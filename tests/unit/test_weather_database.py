"""Database tests using moto; no real AWS resources are created."""
from dataclasses import replace

import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from stack.clients import AwsClients
from stack.database import (
    create_database,
    database_create_request,
    delete_database,
    find_database,
)
from stack.weather_config import WeatherSettings


@pytest.fixture
def database_lab(tmp_path, monkeypatch):
    """Provide fake credentials, mocked services, and isolated settings."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")

    with mock_aws():
        aws = AwsClients.create("us-east-2")
        vpc_id = aws.ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
        app_group = aws.ec2.create_security_group(
            GroupName="test-weather-app",
            Description="Mock app group",
            VpcId=vpc_id,
        )["GroupId"]

        values = {
            "AWS_REGION": "us-east-2",
            "AMI_ID": "ami-12345678",
            "KEY_NAME": "test-key",
            "INSTANCE_TYPE": "t3.micro",
            "APP_PORT": "3000",
            "DB_PORT": "5432",
            "APP_SECURITY_GROUP_ID": app_group,
            "ALB_NAME": "test-weather-alb",
            "ALB_SG_NAME": "test-weather-alb-sg",
            "AZ_A": "us-east-2a",
            "AZ_B": "us-east-2b",
            "DB_INSTANCE_ID": "test-weather-db",
            "DB_NAME": "weather",
            "DB_USER": "weatherapp",
            "DB_SG_NAME": "test-weather-db-sg",
            "DB_SUBNET_GROUP_NAME": "test-weather-db-subnets",
            "DB_PASSWORD_PARAM": "/test-weather/db-password",
            "DB_INSTANCE_CLASS": "db.t4g.micro",
            "CACHE_SECONDS": "600",
            "GEMINI_PARAM_NAME": "/test-weather/gemini-api-key",
            "GEMINI_MODEL": "test-model",
            "KEY_CACHE_SECONDS": "60",
            "CONTACT_EMAIL": "test@example.com",
        }
        for prefix, port in (("WEATHER", "8080"), ("ADVISOR", "8081")):
            name = prefix.lower()
            for suffix in (
                "ROLE_NAME", "PROFILE_NAME", "LT_NAME",
                "TG_NAME", "ASG_NAME",
            ):
                values[f"{prefix}_{suffix}"] = (
                    f"test-{name}-{suffix.lower().replace('_', '-')}"
                )
            values[f"{prefix}_LISTENER_PORT"] = port

        settings = WeatherSettings.from_values(values, base_dir=tmp_path)
        yield aws, settings


def test_database_required_settings(database_lab):
    """The mocked RDS instance has all required storage/privacy settings."""
    aws, settings = database_lab
    create_database(aws, settings)
    instance = find_database(aws, settings)

    assert instance["DBInstanceClass"] == "db.t4g.micro"
    assert instance["AllocatedStorage"] == 20
    assert instance["BackupRetentionPeriod"] == 0
    assert instance["MultiAZ"] is False
    assert instance["PubliclyAccessible"] is False
    assert instance["StorageEncrypted"] is True
    assert instance["DeletionProtection"] is False


def test_database_security_group_has_only_app_source(database_lab):
    """Only the app group is allowed on 5432; no IPv4/IPv6 CIDRs."""
    aws, settings = database_lab
    outputs = create_database(aws, settings)
    group = aws.ec2.describe_security_groups(
        GroupIds=[outputs["DB_SECURITY_GROUP_ID"]]
    )["SecurityGroups"][0]

    rules = group["IpPermissions"]
    assert len(rules) == 1
    rule = rules[0]
    assert rule["IpProtocol"] == "tcp"
    assert rule["FromPort"] == 5432
    assert rule["ToPort"] == 5432
    assert not rule.get("IpRanges")
    assert not rule.get("Ipv6Ranges")
    assert {
        source["GroupId"] for source in rule["UserIdGroupPairs"]
    } == {settings.app_sg_id}


def test_database_create_twice_has_no_duplicates(database_lab):
    """Repeated creation preserves the instance, group, and password version."""
    aws, settings = database_lab
    first = create_database(aws, settings)
    first_version = aws.ssm.get_parameter(
        Name=settings.db_password_param
    )["Parameter"]["Version"]

    second = create_database(aws, settings)

    assert first == second
    assert len(aws.rds.describe_db_instances()["DBInstances"]) == 1
    assert len(
        aws.rds.describe_db_subnet_groups()["DBSubnetGroups"]
    ) == 1
    assert aws.ssm.get_parameter(
        Name=settings.db_password_param
    )["Parameter"]["Version"] == first_version


def test_database_delete_removes_resources_and_is_repeatable(database_lab):
    """Cleanup leaves no DB, snapshots, backups, password, or output file."""
    aws, settings = database_lab
    outputs = create_database(aws, settings)
    delete_database(aws, settings)
    delete_database(aws, settings)

    assert aws.rds.describe_db_instances()["DBInstances"] == []
    assert aws.rds.describe_db_snapshots()["DBSnapshots"] == []
    assert aws.rds.describe_db_instance_automated_backups()[
        "DBInstanceAutomatedBackups"
    ] == []
    assert aws.rds.describe_db_subnet_groups()["DBSubnetGroups"] == []
    assert not (settings.base_dir / "db_outputs.env").exists()

    with pytest.raises(ClientError) as caught:
        aws.ssm.get_parameter(Name=settings.db_password_param)
    assert caught.value.response["Error"]["Code"] == "ParameterNotFound"

    groups = aws.ec2.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": [settings.db_sg_name]}]
    )["SecurityGroups"]
    assert groups == []


def test_database_secret_not_written_or_printed(database_lab, capsys):
    """The generated password stays out of outputs and local files."""
    aws, settings = database_lab
    create_database(aws, settings)
    password = aws.ssm.get_parameter(
        Name=settings.db_password_param,
        WithDecryption=True,
    )["Parameter"]["Value"]

    assert len(password) == 32
    assert all(character in "0123456789abcdef" for character in password)
    assert password not in capsys.readouterr().out
    assert password not in (
        settings.base_dir / "db_outputs.env"
    ).read_text(encoding="utf-8")


def test_database_request_uses_configured_class(database_lab):
    """The request builder reads the class from configuration."""
    _, settings = database_lab
    changed = replace(settings, db_instance_class="db.t3.micro")
    request = database_create_request(changed, "sg-test", "dummy-password")
    assert request["DBInstanceClass"] == "db.t3.micro"
    assert request["BackupRetentionPeriod"] == 0
    assert request["StorageEncrypted"] is True


def test_database_port_comes_from_configuration(database_lab):
    """The RDS request and ingress rule follow the configured DB port."""
    from stack.database import database_ingress
    _, settings = database_lab
    changed = replace(settings, db_port=5544)
    request = database_create_request(changed, "sg-test", "dummy-password")
    rule = database_ingress(changed.app_sg_id, changed.db_port)[0]
    assert request["Port"] == 5544
    assert rule["FromPort"] == rule["ToPort"] == 5544
