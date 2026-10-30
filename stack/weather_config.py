"""Configuration for the weather/advisor lab."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import ConfigError, Tier, load_dotenv


@dataclass(frozen=True)
class WeatherSettings:
    region: str
    ami_id: str
    key_name: str
    instance_type: str
    app_sg_id: str
    alb_name: str
    alb_sg_name: str
    az_a: str
    az_b: str
    weather: Tier
    advisor: Tier
    db_instance_id: str
    db_name: str
    db_user: str
    db_sg_name: str
    db_subnet_group_name: str
    db_password_param: str
    db_instance_class: str
    cache_seconds: int
    gemini_param_name: str
    gemini_model: str
    key_cache_seconds: int
    contact_email: str
    base_dir: Path
    app_port: int
    db_port: int

    @property
    def tiers(self) -> tuple[Tier, Tier]:
        """Return the two application tiers."""
        return self.weather, self.advisor

    def tier(self, name: str) -> Tier:
        """Find a tier by its service name."""
        return {"weather": self.weather, "advisor": self.advisor}[name]

    @classmethod
    def from_values(
        cls, values: dict[str, str], base_dir: str | Path = "."
    ) -> "WeatherSettings":
        """Validate and convert configuration values."""
        required = [
            "AWS_REGION", "AMI_ID", "KEY_NAME", "INSTANCE_TYPE", "APP_PORT", "DB_PORT",
            "APP_SECURITY_GROUP_ID", "ALB_NAME", "ALB_SG_NAME",
            "AZ_A", "AZ_B", "DB_INSTANCE_ID", "DB_NAME", "DB_USER",
            "DB_SG_NAME", "DB_SUBNET_GROUP_NAME", "DB_PASSWORD_PARAM",
            "DB_INSTANCE_CLASS", "CACHE_SECONDS", "GEMINI_PARAM_NAME",
            "GEMINI_MODEL", "KEY_CACHE_SECONDS", "CONTACT_EMAIL",
        ]
        tier_suffixes = [
            "ROLE_NAME", "PROFILE_NAME", "LT_NAME", "TG_NAME",
            "ASG_NAME", "LISTENER_PORT",
        ]
        for prefix in ("WEATHER", "ADVISOR"):
            required.extend(f"{prefix}_{suffix}" for suffix in tier_suffixes)

        missing = [key for key in required if not values.get(key)]
        if missing:
            raise ConfigError("Missing settings: " + ", ".join(missing))

        if values["AZ_A"] == values["AZ_B"]:
            raise ConfigError("AZ_A and AZ_B must be different.")

        base = Path(base_dir).resolve()

        def make_tier(prefix: str) -> Tier:
            """Build a tier using the existing lab05 Tier class."""
            try:
                port = int(values[f"{prefix}_LISTENER_PORT"])
            except ValueError as error:
                raise ConfigError(
                    f"{prefix}_LISTENER_PORT must be an integer."
                ) from error
            if not 1 <= port <= 65535:
                raise ConfigError(f"{prefix}_LISTENER_PORT is invalid.")
            return Tier(
                name=prefix.lower(),
                role_name=values[f"{prefix}_ROLE_NAME"],
                profile_name=values[f"{prefix}_PROFILE_NAME"],
                lt_name=values[f"{prefix}_LT_NAME"],
                tg_name=values[f"{prefix}_TG_NAME"],
                asg_name=values[f"{prefix}_ASG_NAME"],
                listener_port=port,
                app_dir=base / f"{prefix.lower()}-app",
            )

        weather = make_tier("WEATHER")
        advisor = make_tier("ADVISOR")
        if weather.listener_port == advisor.listener_port:
            raise ConfigError("Weather and advisor listener ports must differ.")

        try:
            cache_seconds = int(values["CACHE_SECONDS"])
            key_cache_seconds = int(values["KEY_CACHE_SECONDS"])
        except ValueError as error:
            raise ConfigError("Cache settings must be integers.") from error

        if cache_seconds <= 0 or key_cache_seconds <= 0:
            raise ConfigError("Cache settings must be positive.")

        return cls(
            region=values["AWS_REGION"],
            ami_id=values["AMI_ID"],
            key_name=values["KEY_NAME"],
            instance_type=values["INSTANCE_TYPE"],
            app_sg_id=values["APP_SECURITY_GROUP_ID"],
            alb_name=values["ALB_NAME"],
            alb_sg_name=values["ALB_SG_NAME"],
            az_a=values["AZ_A"],
            az_b=values["AZ_B"],
            weather=weather,
            advisor=advisor,
            db_instance_id=values["DB_INSTANCE_ID"],
            db_name=values["DB_NAME"],
            db_user=values["DB_USER"],
            db_sg_name=values["DB_SG_NAME"],
            db_subnet_group_name=values["DB_SUBNET_GROUP_NAME"],
            db_password_param=values["DB_PASSWORD_PARAM"],
            db_instance_class=values["DB_INSTANCE_CLASS"],
            cache_seconds=cache_seconds,
            gemini_param_name=values["GEMINI_PARAM_NAME"],
            gemini_model=values["GEMINI_MODEL"],
            key_cache_seconds=key_cache_seconds,
            contact_email=values["CONTACT_EMAIL"],
            base_dir=base,
            app_port=int(values["APP_PORT"]),
            db_port=int(values["DB_PORT"]),
        )

    @classmethod
    def from_file(cls, path: str | Path = ".env") -> "WeatherSettings":
        """Load settings relative to the configuration file."""
        path = Path(path).resolve()
        return cls.from_values(load_dotenv(path), base_dir=path.parent)
