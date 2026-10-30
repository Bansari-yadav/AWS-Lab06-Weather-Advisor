"""Test Gemini fallback, then restore the real key."""
import getpass
import json
import subprocess
import sys
import time
import warnings
from pathlib import Path

import requests

from stack.clients import AwsClients
from stack.config import load_dotenv
from stack.weather_config import WeatherSettings

settings = WeatherSettings.from_file()
aws = AwsClients.create(settings.region)
outputs = load_dotenv("stack_outputs.env")
url = (
    f"http://{outputs['ALB_DNS_NAME']}:"
    f"{settings.advisor.listener_port}/advice?zip=60616"
)

warnings.simplefilter("error", getpass.GetPassWarning)
real_key = getpass.getpass(
    "Paste your CURRENT replacement Gemini key (hidden): "
).strip()
if not real_key:
    raise SystemExit("No key entered. Nothing changed.")

changed = False
results = []
try:
    aws.ssm.put_parameter(
        Name=settings.gemini_param_name,
        Type="SecureString",
        Value="not-a-real-key",
        Overwrite=True,
    )
    changed = True
    print("Invalid test key stored. Waiting 70 seconds...", flush=True)
    time.sleep(70)

    for attempt in range(1, 4):
        response = requests.get(url, timeout=75)
        body = response.json()
        result = {
            "attempt": attempt,
            "status": response.status_code,
            "source": body.get("source"),
            "advice": body.get("advice"),
        }
        results.append(result)
        print(json.dumps(result, indent=2), flush=True)

    Path("evidence/H8_fallback_answers.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    input(
        "Collect the ADVISOR gemini_error journal screenshot, "
        "then press Enter HERE to restore the real key: "
    )
finally:
    if changed:
        aws.ssm.put_parameter(
            Name=settings.gemini_param_name,
            Type="SecureString",
            Value=real_key,
            Overwrite=True,
        )
        print("Real key restored. Waiting 70 seconds...", flush=True)
        time.sleep(70)
    real_key = None

print("Running the smoke test after restoration...", flush=True)
result = subprocess.run(
    [sys.executable, "testing/app_smoke_test.py"],
    capture_output=True, text=True,
)
print(result.stdout)
print(result.stderr)
Path("evidence/H8_restored_smoke_test.txt").write_text(
    result.stdout + result.stderr, encoding="utf-8"
)
sys.exit(result.returncode)
