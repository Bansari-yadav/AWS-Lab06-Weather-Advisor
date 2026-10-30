"""Integration tests against the deployed weather stack."""
import socket

import boto3
import pytest
import requests

from stack.clients import AwsClients
from stack.config import load_dotenv
from stack.weather_config import WeatherSettings
from stack.weather_policies import parameter_arn
from testing.app_smoke_test import run_checks

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live_lab():
    """Load the weather lab without using the old lab05 fixtures."""
    config = WeatherSettings.from_file()
    outputs = load_dotenv("stack_outputs.env")
    db = load_dotenv("db_outputs.env")
    aws = AwsClients.create(config.region)
    host = outputs["ALB_DNS_NAME"]
    weather = f"http://{host}:{config.weather.listener_port}"
    return config, outputs, db, aws, weather


def test_both_target_groups_healthy(live_lab):
    config, outputs, db, aws, weather = live_lab
    for key in ("WEATHER_TG_ARN", "ADVISOR_TG_ARN"):
        targets = aws.elbv2.describe_target_health(
            TargetGroupArn=outputs[key]
        )["TargetHealthDescriptions"]
        assert targets
        assert all(
            target["TargetHealth"]["State"] == "healthy"
            for target in targets
        )


def test_forecast_miss_then_hit_and_history(live_lab):
    config, outputs, db, aws, weather = live_lab
    # Find a genuinely fresh ZIP rather than assuming one is uncached.
    for zip_code in (
        "02108", "80202", "30303", "85001", "97201", "55401", "20001"
    ):
        response = requests.get(
            weather + "/weather", params={"zip": zip_code}, timeout=75
        )
        assert response.status_code == 200
        if response.json().get("cache") == "miss":
            break
    else:
        pytest.fail("All candidate ZIPs are cached; retry after cache expiry.")

    repeat = requests.get(
        weather + "/weather", params={"zip": zip_code}, timeout=75
    )
    assert repeat.status_code == 200
    assert repeat.json()["cache"] == "hit"

    history = requests.get(weather + "/history", timeout=15)
    assert history.status_code == 200
    assert any(
        row["zip"] == zip_code for row in history.json()["lookups"]
    )


@pytest.mark.parametrize("zip_code,expected", [("abc", 400), ("00000", 404)])
def test_weather_error_statuses(live_lab, zip_code, expected):
    weather = live_lab[4]
    assert requests.get(
        weather + "/weather", params={"zip": zip_code}, timeout=75
    ).status_code == expected


def test_all_nine_smoke_checks():
    results = run_checks()
    assert len(results) == 9
    assert all(ok for _, ok in results), results


@pytest.mark.parametrize("tier_name", ["weather", "advisor"])
def test_application_access_only_through_alb(live_lab, tier_name):
    config, outputs, db, aws, weather = live_lab
    tier = config.tier(tier_name)
    reservations = aws.ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [f"{tier_name}-app"]},
        {"Name": "instance-state-name", "Values": ["running"]},
        {"Name": "instance.group-id", "Values": [config.app_sg_id]},
    ])["Reservations"]
    instances = [
        item for reservation in reservations
        for item in reservation["Instances"]
    ]
    assert len(instances) == 1
    public_ip = instances[0]["PublicIpAddress"]

    # A timeout proves blocked traffic; unrelated client errors must fail.
    with pytest.raises(requests.exceptions.ConnectTimeout):
        requests.get(
            f"http://{public_ip}:{config.app_port}/", timeout=5
        )

    assert requests.get(
        f"http://{outputs['ALB_DNS_NAME']}:{tier.listener_port}/",
        timeout=15,
    ).status_code == 200


def test_database_port_unreachable_from_computer(live_lab):
    config, outputs, db, aws, weather = live_lab
    with pytest.raises(TimeoutError):
        with socket.create_connection((db["DB_HOST"], config.db_port), timeout=6):
            pass


def test_each_role_reads_only_its_own_secret(live_lab):
    config, outputs, db, aws, weather = live_lab
    account = boto3.client(
        "sts", region_name=config.region
    ).get_caller_identity()["Account"]

    for tier in config.tiers:
        role_arn = aws.iam.get_role(
            RoleName=tier.role_name
        )["Role"]["Arn"]
        own = (
            config.db_password_param if tier.name == "weather"
            else config.gemini_param_name
        )
        for name in (config.db_password_param, config.gemini_param_name):
            decision = aws.iam.simulate_principal_policy(
                PolicySourceArn=role_arn,
                ActionNames=["ssm:GetParameter"],
                ResourceArns=[
                    parameter_arn(config.region, account, name)
                ],
            )["EvaluationResults"][0]["EvalDecision"]
            assert decision == (
                "allowed" if name == own else "implicitDeny"
            )


def test_database_tls_and_backup_configuration(live_lab):
    config, outputs, db, aws, weather = live_lab
    instance = aws.rds.describe_db_instances(
        DBInstanceIdentifier=config.db_instance_id
    )["DBInstances"][0]
    assert instance["BackupRetentionPeriod"] == 0
    assert instance["StorageEncrypted"] is True
    assert instance["PubliclyAccessible"] is False
    assert instance["MultiAZ"] is False

    snapshots = []
    for page in aws.rds.get_paginator("describe_db_snapshots").paginate():
        snapshots.extend(
            item for item in page["DBSnapshots"]
            if item["DBInstanceIdentifier"] == config.db_instance_id
        )
    assert snapshots == []

    backups = []
    for page in aws.rds.get_paginator(
        "describe_db_instance_automated_backups"
    ).paginate():
        backups.extend(
            item for item in page["DBInstanceAutomatedBackups"]
            if item["DBInstanceIdentifier"] == config.db_instance_id
        )
    assert backups == []

    # A working cache exercises the app's configured verified-TLS connection.
    for _ in range(2):
        response = requests.get(weather + "/weather?zip=60616", timeout=75)
        assert response.status_code == 200
    assert response.json()["cache"] == "hit"
