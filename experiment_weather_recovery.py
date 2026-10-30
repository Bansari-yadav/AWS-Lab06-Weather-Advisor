"""Measure weather-instance replacement and advisor behavior."""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

from stack.clients import AwsClients
from stack.config import load_dotenv
from stack.weather_config import WeatherSettings

settings = WeatherSettings.from_file()
aws = AwsClients.create(settings.region)
outputs = load_dotenv("stack_outputs.env")
host = outputs["ALB_DNS_NAME"]
weather = f"http://{host}:{settings.weather.listener_port}"
advisor = f"http://{host}:{settings.advisor.listener_port}"
report = {"weather_observations": [], "advisor_observations": []}
stop = threading.Event()
outage = threading.Event()


def get(url, timeout):
    try:
        response = requests.get(url, timeout=timeout)
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return response.status_code, body
    except requests.RequestException as error:
        return 0, {"error": type(error).__name__}


def watch_advisor():
    outage.wait()
    while not stop.is_set():
        status, body = get(advisor + "/advice?zip=33101", 30)
        home_status, _ = get(advisor + "/", 5)
        item = {
            "seconds": round(time.monotonic() - started, 1),
            "advice_status": status,
            "advice_error": body.get("error") if isinstance(body, dict) else body,
            "homepage_status": home_status,
        }
        report["advisor_observations"].append(item)
        print("ADVISOR:", json.dumps(item), flush=True)
        stop.wait(5)


status, _ = get(weather + "/weather?zip=60616", 75)
if status != 200:
    raise SystemExit("Weather baseline failed. Nothing terminated.")

group = aws.autoscaling.describe_auto_scaling_groups(
    AutoScalingGroupNames=[settings.weather.asg_name]
)["AutoScalingGroups"][0]
if len(group["Instances"]) != 1:
    raise SystemExit("Expected exactly one weather instance. Nothing terminated.")

victim = group["Instances"][0]["InstanceId"]
report["terminated_instance"] = victim
aws.autoscaling.terminate_instance_in_auto_scaling_group(
    InstanceId=victim,
    ShouldDecrementDesiredCapacity=False,
)
started = time.monotonic()
print("Weather instance termination requested:", victim, flush=True)

observer = threading.Thread(target=watch_advisor, daemon=True)
observer.start()

try:
    while time.monotonic() - started < 600:
        status, body = get(weather + "/weather?zip=60616", 5)
        seconds = round(time.monotonic() - started, 1)
        item = {"seconds": seconds, "status": status}
        report["weather_observations"].append(item)
        print("WEATHER:", json.dumps(item), flush=True)

        if status != 200:
            outage.set()

        if outage.is_set() and status == 200:
            current = aws.autoscaling.describe_auto_scaling_groups(
                AutoScalingGroupNames=[settings.weather.asg_name]
            )["AutoScalingGroups"][0]
            replacements = [
                instance["InstanceId"] for instance in current["Instances"]
                if instance["InstanceId"] != victim
            ]
            if replacements:
                report["replacement_instances"] = replacements
                report["recovery_seconds"] = seconds
                report["recovered_within_300_seconds"] = seconds <= 300
                report["post_recovery_cache"] = (
                    body.get("cache") if isinstance(body, dict) else None
                )
                break
        time.sleep(5)
finally:
    stop.set()
    outage.set()
    observer.join(timeout=40)
    Path("evidence/H9_weather_recovery.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

print("\nRECOVERY SUMMARY")
print(json.dumps({
    key: value for key, value in report.items()
    if key not in ("weather_observations", "advisor_observations")
}, indent=2))

if "recovery_seconds" not in report:
    raise SystemExit("Recovery not confirmed. Send the output; do not redeploy.")

result = subprocess.run(
    [sys.executable, "testing/app_smoke_test.py"],
    capture_output=True, text=True,
)
print(result.stdout)
print(result.stderr)
Path("evidence/H9_restored_smoke_test.txt").write_text(
    result.stdout + result.stderr, encoding="utf-8"
)
sys.exit(result.returncode)
