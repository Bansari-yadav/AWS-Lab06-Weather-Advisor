"""Test the weather stack with simulated AWS services."""
import base64
from dataclasses import replace
from pathlib import Path

import pytest

from tests.unit.test_weather_database import database_lab
from stack import balancer, weather_compute
from stack.database import create_database, find_database
from stack.weather_policies import secret_policy
from stack.weather_runner import create_weather_stack, delete_weather_stack


@pytest.fixture
def weather_lab(database_lab):
    """Prepare mocked infrastructure and copies of the application files."""
    aws, settings = database_lab
    project = Path(__file__).resolve().parents[2]

    for tier in settings.tiers:
        tier.app_dir.mkdir()
        for filename in ("app.js", "package.json"):
            source = project / f"{tier.name}-app" / filename
            (tier.app_dir / filename).write_text(
                source.read_text(encoding="utf-8-sig"),
                encoding="utf-8",
            )

    image_id = aws.ec2.register_image(
        Name="weather-unit-test-image",
        Architecture="x86_64",
        VirtualizationType="hvm",
        RootDeviceName="/dev/xvda",
    )["ImageId"]
    aws.ec2.create_key_pair(KeyName=settings.key_name)
    settings = replace(settings, ami_id=image_id)

    aws.ssm.put_parameter(
        Name=settings.gemini_param_name,
        Value="mock-key-for-unit-tests-only",
        Type="SecureString",
    )
    return aws, settings


def test_roles_have_separate_secret_policies(weather_lab):
    """Each policy allows only GetParameter on its own secret."""
    _, settings = weather_lab
    for tier, own_name, other_name in (
        (settings.weather, settings.db_password_param,
         settings.gemini_param_name),
        (settings.advisor, settings.gemini_param_name,
         settings.db_password_param),
    ):
        policy = secret_policy(settings, tier, "123456789012")
        assert policy == {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["ssm:GetParameter"],
                "Resource": (
                    f"arn:aws:ssm:{settings.region}:123456789012:"
                    f"parameter/{own_name.lstrip('/')}"
                ),
            }],
        }
        assert other_name not in str(policy)


@pytest.mark.parametrize("tier_name", ["weather", "advisor"])
def test_user_data_under_16kb_and_secret_free(weather_lab, tier_name):
    """Check payload size and tier-specific startup configuration."""
    _, settings = weather_lab
    script = weather_compute.build_user_data(
        settings, settings.tier(tier_name),
        "test-alb.invalid", "test-db.invalid"
    )
    assert len(script.encode("utf-8")) < 16384
    assert "mock-key-for-unit-tests-only" not in script
    assert 'Environment="GEMINI_API_KEY=' not in script
    assert 'Environment="DB_PASSWORD=' not in script

    if tier_name == "weather":
        assert "test-db.invalid" in script
        assert settings.db_password_param in script
        assert "postgresql15" in script
        assert "global-bundle.pem" in script
    else:
        assert (
            f"http://test-alb.invalid:{settings.weather.listener_port}"
        ) in script
        assert settings.gemini_param_name in script


def test_launch_template_create_twice_has_one_version(weather_lab):
    """Repeated creation with unchanged settings must reuse its version."""
    aws, settings = weather_lab
    for tier in settings.tiers:
        first = weather_compute.ensure_launch_template(
            aws, settings, tier, "test-alb.invalid", "test-db.invalid"
        )
        second = weather_compute.ensure_launch_template(
            aws, settings, tier, "test-alb.invalid", "test-db.invalid"
        )
        assert first == second
        assert len(aws.ec2.describe_launch_template_versions(
            LaunchTemplateName=tier.lt_name
        )["LaunchTemplateVersions"]) == 1


def test_stack_order_repeat_creation_and_cleanup(weather_lab, monkeypatch):
    """Prove ALB-first ordering, repeat creation, and repeat cleanup."""
    aws, settings = weather_lab
    db_outputs = create_database(aws, settings)
    account = "123456789012"
    original = weather_compute.ensure_launch_template
    checked_tiers = []

    def checked_template(aws_arg, settings_arg, tier, alb_dns, db_host):
        """Assert the ALB exists before a launch template is generated."""
        lb = balancer.find_load_balancer(aws_arg, settings_arg.alb_name)
        assert lb is not None
        assert lb["DNSName"] == alb_dns
        assert db_host == db_outputs["DB_HOST"]
        checked_tiers.append(tier.name)
        return original(aws_arg, settings_arg, tier, alb_dns, db_host)

    monkeypatch.setattr(
        weather_compute, "ensure_launch_template", checked_template
    )
    first = create_weather_stack(
        aws, settings, account, iam_wait=0, sleep=lambda _: None
    )
    second = create_weather_stack(
        aws, settings, account, iam_wait=0, sleep=lambda _: None
    )
    assert first == second
    assert checked_tiers == ["weather", "advisor", "weather", "advisor"]
    assert len(aws.elbv2.describe_load_balancers()["LoadBalancers"]) == 1
    assert len(aws.elbv2.describe_target_groups()["TargetGroups"]) == 2
    assert len(aws.autoscaling.describe_auto_scaling_groups()[
        "AutoScalingGroups"
    ]) == 2

    password = aws.ssm.get_parameter(
        Name=settings.db_password_param, WithDecryption=True
    )["Parameter"]["Value"]

    for tier in settings.tiers:
        actual = aws.iam.get_role_policy(
            RoleName=tier.role_name, PolicyName=tier.policy_name
        )["PolicyDocument"]
        assert actual == secret_policy(settings, tier, account)
        versions = aws.ec2.describe_launch_template_versions(
            LaunchTemplateName=tier.lt_name
        )["LaunchTemplateVersions"]
        assert len(versions) == 1
        script = base64.b64decode(
            versions[0]["LaunchTemplateData"]["UserData"]
        ).decode("utf-8")
        assert password not in script
        assert "mock-key-for-unit-tests-only" not in script

    delete_weather_stack(aws, settings, sleep=lambda _: None)
    delete_weather_stack(aws, settings, sleep=lambda _: None)

    assert aws.elbv2.describe_load_balancers()["LoadBalancers"] == []
    assert aws.elbv2.describe_target_groups()["TargetGroups"] == []
    assert aws.autoscaling.describe_auto_scaling_groups()[
        "AutoScalingGroups"
    ] == []
    assert aws.ec2.describe_launch_templates()["LaunchTemplates"] == []
    assert not (settings.base_dir / "stack_outputs.env").exists()
    assert not (settings.base_dir / "stack_outputs.json").exists()

    roles = {role["RoleName"] for role in aws.iam.list_roles()["Roles"]}
    assert settings.weather.role_name not in roles
    assert settings.advisor.role_name not in roles

    assert find_database(aws, settings) is not None
    assert aws.ssm.get_parameter(
        Name=settings.gemini_param_name
    )["Parameter"]["Type"] == "SecureString"
