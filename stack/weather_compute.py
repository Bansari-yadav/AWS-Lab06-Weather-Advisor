"""Build EC2 startup scripts for the weather and advisor services."""
import base64
import json

from .config import Tier
from .weather_config import WeatherSettings


def encoded_source(path):
    """Encode source as UTF-8 without a BOM and with Linux line endings."""
    text = path.read_text(encoding="utf-8-sig")
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def build_user_data(
    settings: WeatherSettings,
    tier: Tier,
    alb_dns: str,
    db_host: str,
) -> str:
    """Build a boot script containing configuration but no secret values."""
    environment = {
        "PORT": str(settings.app_port),
        "AWS_REGION": settings.region,
    }
    setup = ""

    if tier.name == "weather":
        if not db_host:
            raise ValueError("Weather startup requires a database host.")
        environment.update({
            "NWS_USER_AGENT": (
                f"(itmo-444-544 weather lab, {settings.contact_email})"
            ),
            "DB_HOST": db_host,
            "DB_NAME": settings.db_name,
            "DB_PORT": str(settings.db_port),
            "DB_USER": settings.db_user,
            "DB_PASSWORD_PARAM": settings.db_password_param,
            "CACHE_SECONDS": str(settings.cache_seconds),
        })
        setup = (
            "dnf install -y postgresql15\n"
            "curl -fsS -o /opt/app/rds-ca.pem "
            "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem\n"
        )
    elif tier.name == "advisor":
        if not alb_dns:
            raise ValueError("Advisor startup requires the ALB DNS name.")
        environment.update({
            "WEATHER_URL": (
                f"http://{alb_dns}:{settings.weather.listener_port}"
            ),
            "GEMINI_KEY_PARAM": settings.gemini_param_name,
            "GEMINI_MODEL": settings.gemini_model,
            "KEY_CACHE_SECONDS": str(settings.key_cache_seconds),
        })
    else:
        raise ValueError(f"Unknown tier: {tier.name}")

    environment_lines = "\n".join(
        "Environment=" + json.dumps(f"{key}={value}")
        for key, value in environment.items()
    )
    app_source = encoded_source(tier.app_dir / "app.js")
    package_source = encoded_source(tier.app_dir / "package.json")

    script = f"""#!/bin/bash
set -euo pipefail
dnf update -y
dnf install -y nodejs
mkdir -p /opt/app
{setup}echo "{app_source}" | base64 -d > /opt/app/app.js
echo "{package_source}" | base64 -d > /opt/app/package.json
cd /opt/app
npm install --omit=dev

cat > /etc/systemd/system/{tier.service_name}.service << 'SERVICE'
[Unit]
Description={tier.name.capitalize()} app
After=network.target

[Service]
{environment_lines}
WorkingDirectory=/opt/app
ExecStart=/usr/bin/node /opt/app/app.js
Restart=always
User=ec2-user

[Install]
WantedBy=multi-user.target
SERVICE

chown -R ec2-user:ec2-user /opt/app
systemctl daemon-reload
systemctl enable {tier.service_name}.service
systemctl start {tier.service_name}.service
"""
    if len(script.encode("utf-8")) >= 16384:
        raise ValueError(f"{tier.name} user-data must be under 16 KB.")
    return script


def launch_template_data(
    settings: WeatherSettings,
    tier: Tier,
    alb_dns: str,
    db_host: str,
) -> dict:
    """Build a launch template using configuration and secret-free user-data."""
    user_data = build_user_data(settings, tier, alb_dns, db_host)
    return {
        "ImageId": settings.ami_id,
        "InstanceType": settings.instance_type,
        "KeyName": settings.key_name,
        "SecurityGroupIds": [settings.app_sg_id],
        "IamInstanceProfile": {"Name": tier.profile_name},
        "UserData": base64.b64encode(
            user_data.encode("utf-8")
        ).decode("ascii"),
        "TagSpecifications": [{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": f"{tier.name}-app"}],
        }],
    }


def ensure_launch_template(
    aws,
    settings: WeatherSettings,
    tier: Tier,
    alb_dns: str,
    db_host: str,
) -> int:
    """Create a template; reuse its latest version when nothing changed."""
    from .compute import launch_template_exists

    data = launch_template_data(settings, tier, alb_dns, db_host)

    if not launch_template_exists(aws, tier):
        result = aws.ec2.create_launch_template(
            LaunchTemplateName=tier.lt_name,
            LaunchTemplateData=data,
        )
        return result["LaunchTemplate"]["LatestVersionNumber"]

    latest = aws.ec2.describe_launch_template_versions(
        LaunchTemplateName=tier.lt_name,
        Versions=["$Latest"],
    )["LaunchTemplateVersions"][0]

    existing_data = latest["LaunchTemplateData"]
    if all(existing_data.get(key) == value for key, value in data.items()):
        return latest["VersionNumber"]

    result = aws.ec2.create_launch_template_version(
        LaunchTemplateName=tier.lt_name,
        SourceVersion=str(latest["VersionNumber"]),
        LaunchTemplateData=data,
    )
    return result["LaunchTemplateVersion"]["VersionNumber"]
