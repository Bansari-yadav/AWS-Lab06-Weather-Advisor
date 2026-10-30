"""Collect read-only experiment evidence from the deployed lab."""
import json
import socket
import time
from pathlib import Path

import boto3
import requests
from botocore.exceptions import ClientError

from stack.clients import AwsClients
from stack.config import load_dotenv
from stack.weather_config import WeatherSettings
from stack.weather_policies import parameter_arn

settings = WeatherSettings.from_file()
aws = AwsClients.create(settings.region)
outputs = load_dotenv("stack_outputs.env")
db = load_dotenv("db_outputs.env")
weather = (
    f"http://{outputs['ALB_DNS_NAME']}:"
    f"{settings.weather.listener_port}"
)
evidence = Path("evidence")
failures = []


def save(name, value):
    text = json.dumps(value, indent=2)
    print(text, flush=True)
    (evidence / name).write_text(text, encoding="utf-8")


def collect(label, filename, operation):
    print("\n" + label, flush=True)
    try:
        save(filename, operation())
    except (ClientError, requests.RequestException, OSError,
            ValueError, RuntimeError) as error:
        failures.append(label)
        save(filename, {"error": str(error)})


def history():
    response = requests.get(weather + "/history", timeout=60)
    response.raise_for_status()
    return response.json()


def cache_timing():
    # Choose a ZIP whose first response is genuinely a cache miss.
    attempts = []
    for zip_code in ("98101", "02108", "80202", "30303", "85001"):
        started = time.perf_counter()
        response = requests.get(
            weather + "/weather", params={"zip": zip_code}, timeout=75
        )
        body = response.json()
        first = {
            "zip": zip_code,
            "status": response.status_code,
            "cache": body.get("cache"),
            "seconds": round(time.perf_counter() - started, 3),
        }
        attempts.append(first)
        if response.status_code == 200 and body.get("cache") == "miss":
            started = time.perf_counter()
            second_response = requests.get(
                weather + "/weather",
                params={"zip": zip_code}, timeout=75
            )
            second_body = second_response.json()
            return {
                "first_request": first,
                "second_request": {
                    "zip": zip_code,
                    "status": second_response.status_code,
                    "cache": second_body.get("cache"),
                    "seconds": round(time.perf_counter() - started, 3),
                },
                "earlier_attempts": attempts[:-1],
            }
    raise RuntimeError(
        "No fresh successful cache miss found: " + json.dumps(attempts)
    )


def database_connection():
    try:
        with socket.create_connection((db["DB_HOST"], settings.db_port), timeout=6):
            return {"result": "REACHABLE — unexpected; investigate"}
    except OSError as error:
        return {
            "result": "no connection",
            "error_type": type(error).__name__,
            "detail": str(error),
        }


def permissions():
    account = boto3.client(
        "sts", region_name=settings.region
    ).get_caller_identity()["Account"]
    results = []
    for tier in settings.tiers:
        role_arn = aws.iam.get_role(
            RoleName=tier.role_name
        )["Role"]["Arn"]
        for name in (
            settings.db_password_param, settings.gemini_param_name
        ):
            decision = aws.iam.simulate_principal_policy(
                PolicySourceArn=role_arn,
                ActionNames=["ssm:GetParameter"],
                ResourceArns=[
                    parameter_arn(settings.region, account, name)
                ],
            )["EvaluationResults"][0]["EvalDecision"]
            results.append({
                "role": tier.name,
                "parameter": name,
                "decision": decision,
            })
    return results


def isolation():
    results = []
    for tier in settings.tiers:
        reservations = aws.ec2.describe_instances(Filters=[
            {"Name": "tag:Name", "Values": [f"{tier.name}-app"]},
            {"Name": "instance-state-name", "Values": ["running"]},
            {"Name": "vpc-id", "Values": [outputs["VPC_ID"]]},
        ])["Reservations"]
        instances = [
            instance for reservation in reservations
            for instance in reservation["Instances"]
        ]
        if len(instances) != 1:
            raise RuntimeError(
                f"Expected one running {tier.name} instance."
            )
        public_ip = instances[0].get("PublicIpAddress")
        if not public_ip:
            raise RuntimeError(
                f"No public IP for {tier.name}; record separately."
            )
        try:
            direct = requests.get(
                f"http://{public_ip}:{settings.app_port}/", timeout=5
            )
            direct_result = f"HTTP {direct.status_code} — unexpected"
        except requests.RequestException as error:
            direct_result = "blocked: " + type(error).__name__

        through_alb = requests.get(
            f"http://{outputs['ALB_DNS_NAME']}:{tier.listener_port}/",
            timeout=15,
        )
        results.append({
            "tier": tier.name,
            "direct": direct_result,
            "through_ALB_status": through_alb.status_code,
        })
    return results


collect("H2: Saved history", "H2_history.json", history)
collect("H3: Miss versus hit", "H3_cache_timings.json", cache_timing)
collect("H4: External DB connection", "H4_external_connection.json",
        database_connection)
collect("H5: Both roles against both secrets",
        "H5_iam_simulation.json", permissions)
collect("H6: Direct versus ALB access", "H6_network_isolation.json",
        isolation)

print("\nCollection finished.")
print("Sections with errors:", failures)
