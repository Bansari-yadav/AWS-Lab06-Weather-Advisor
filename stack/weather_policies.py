"""Least-privilege secret policies for the weather and advisor roles."""
from .config import Tier
from .weather_config import WeatherSettings


def parameter_arn(region: str, account_id: str, name: str) -> str:
    """Build an SSM parameter ARN without reading its value."""
    return (
        f"arn:aws:ssm:{region}:{account_id}:"
        f"parameter/{name.lstrip('/')}"
    )


def secret_policy(
    settings: WeatherSettings, tier: Tier, account_id: str
) -> dict:
    """Allow a tier to read exactly its own parameter."""
    parameter_names = {
        "weather": settings.db_password_param,
        "advisor": settings.gemini_param_name,
    }
    if tier.name not in parameter_names:
        raise ValueError(f"Unknown tier: {tier.name}")

    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["ssm:GetParameter"],
            "Resource": parameter_arn(
                settings.region,
                account_id,
                parameter_names[tier.name],
            ),
        }],
    }
