"""Run the database-isolation experiment and restore access afterward."""
import json
import time
from pathlib import Path

import requests

from stack.clients import AwsClients
from stack.config import load_dotenv
from stack.database import database_ingress
from stack.weather_config import WeatherSettings

settings = WeatherSettings.from_file()
aws = AwsClients.create(settings.region)
outputs = load_dotenv("stack_outputs.env")
db = load_dotenv("db_outputs.env")
base = (
    f"http://{outputs['ALB_DNS_NAME']}:"
    f"{settings.weather.listener_port}"
)
evidence = {}
revoked = False

try:
    aws.ec2.revoke_security_group_ingress(
        GroupId=db["DB_SECURITY_GROUP_ID"],
        IpPermissions=database_ingress(settings.app_sg_id, settings.db_port),
    )
    revoked = True
    print("Database access temporarily blocked.", flush=True)
    input(
        "Restart weather in the AWS browser terminal, "
        "then return HERE and press Enter: "
    )
    time.sleep(5)

    response = requests.get(base + "/weather?zip=60616", timeout=75)
    evidence["weather_during_outage"] = {
        "status": response.status_code,
        "body": response.json(),
    }
    history = requests.get(base + "/history", timeout=15)
    evidence["history_during_outage"] = {
        "status": history.status_code,
        "body": history.json(),
    }
    print(json.dumps(evidence, indent=2), flush=True)
    Path("evidence/H7_database_failure.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )
    input(
        "Collect the db_error log in the browser terminal, "
        "then return HERE and press Enter to restore access: "
    )
finally:
    if revoked:
        aws.ec2.authorize_security_group_ingress(
            GroupId=db["DB_SECURITY_GROUP_ID"],
            IpPermissions=database_ingress(settings.app_sg_id, settings.db_port),
        )
        print("Database rule restored. Waiting 35 seconds...", flush=True)
        time.sleep(35)

response = requests.get(base + "/weather?zip=60616", timeout=75)
evidence["after_restoration"] = {
    "status": response.status_code,
    "body": response.json(),
}
Path("evidence/H7_database_failure.json").write_text(
    json.dumps(evidence, indent=2), encoding="utf-8"
)
print("AFTER RESTORATION:")
print(json.dumps(evidence["after_restoration"], indent=2))
