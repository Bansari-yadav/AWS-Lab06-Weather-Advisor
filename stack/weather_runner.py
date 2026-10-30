"""Build the weather/advisor infrastructure in dependency order."""
import json
import time

from . import balancer, network, scaling
from . import weather_compute, weather_iam
from .config import load_dotenv
from .database import find_database
from .network import StackError


def check_prerequisites(aws, settings):
    """Require the Gemini parameter and an available database."""
    parameters = aws.ssm.describe_parameters(
        ParameterFilters=[{
            "Key": "Name",
            "Option": "Equals",
            "Values": [settings.gemini_param_name],
        }]
    )["Parameters"]
    if not parameters or parameters[0]["Type"] != "SecureString":
        raise StackError(
            "The Gemini SecureString parameter is missing. Complete Part C."
        )

    output_path = settings.base_dir / "db_outputs.env"
    if not output_path.is_file():
        raise StackError(
            "db_outputs.env is missing. Run create_database.py first."
        )

    database = find_database(aws, settings)
    if database is None or database["DBInstanceStatus"] != "available":
        raise StackError("The database must be available before deployment.")

    outputs = load_dotenv(output_path)
    db_host = database["Endpoint"]["Address"]
    if outputs.get("DB_HOST") != db_host:
        raise StackError(
            "db_outputs.env does not match the current database endpoint."
        )
    return db_host


def create_weather_stack(
    aws, settings, account_id, iam_wait=15, sleep=time.sleep
):
    """Create both tiers and save nonsecret resource identifiers."""
    print("Checking the Gemini parameter and database...")
    db_host = check_prerequisites(aws, settings)

    print("Ensuring IAM roles and instance profiles...")
    for tier in settings.tiers:
        weather_iam.ensure_role_and_profile(
            aws, settings, tier, account_id
        )

    print(f"Waiting {iam_wait} seconds for IAM propagation...")
    sleep(iam_wait)

    print("Finding the VPC and subnets...")
    vpc_id = network.default_vpc_id(aws)
    subnet_a = network.subnet_in_az(aws, vpc_id, settings.az_a)
    subnet_b = network.subnet_in_az(aws, vpc_id, settings.az_b)

    print("Ensuring security groups...")
    alb_sg_id = network.ensure_alb_security_group(
        aws, settings, vpc_id
    )
    network.restrict_app_security_group(
        aws, settings, alb_sg_id
    )

    print("Ensuring target groups...")
    target_groups = {
        tier.name: balancer.ensure_target_group(
            aws, settings, tier, vpc_id
        )
        for tier in settings.tiers
    }

    print("Ensuring the ALB before building launch templates...")
    alb_arn, alb_dns = balancer.ensure_load_balancer(
        aws, settings, [subnet_a, subnet_b], alb_sg_id
    )

    for tier in settings.tiers:
        balancer.ensure_listener(
            aws, alb_arn, tier.listener_port, target_groups[tier.name]
        )

    print("Ensuring launch templates...")
    for tier in settings.tiers:
        weather_compute.ensure_launch_template(
            aws, settings, tier, alb_dns, db_host
        )

    print("Ensuring Auto Scaling Groups...")
    for tier in settings.tiers:
        scaling.ensure_asg(
            aws, tier, target_groups[tier.name], [subnet_a, subnet_b]
        )

    outputs = {
        "VPC_ID": vpc_id,
        "SUBNET_A": subnet_a,
        "SUBNET_B": subnet_b,
        "ALB_SECURITY_GROUP_ID": alb_sg_id,
        "ALB_ARN": alb_arn,
        "ALB_DNS_NAME": alb_dns,
        "WEATHER_TG_ARN": target_groups["weather"],
        "ADVISOR_TG_ARN": target_groups["advisor"],
    }

    (settings.base_dir / "stack_outputs.env").write_text(
        "".join(f"{key}={value}\n" for key, value in outputs.items()),
        encoding="utf-8",
    )
    (settings.base_dir / "stack_outputs.json").write_text(
        json.dumps(outputs, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Stack creation complete.")
    print(
        f"Weather: http://{alb_dns}:"
        f"{settings.weather.listener_port}/weather?zip=60616"
    )
    print(
        f"Advisor: http://{alb_dns}:{settings.advisor.listener_port}/"
    )
    print("Wait for both target groups to become healthy before testing.")
    return outputs


def delete_weather_stack(aws, settings, sleep=time.sleep):
    """Remove the app stack; leave the database and Gemini parameter intact."""
    from .compute import delete_launch_template

    print("Deleting Auto Scaling Groups and their instances...")
    for tier in settings.tiers:
        scaling.delete_asg(aws, tier.asg_name, sleep=sleep)

    remaining = [
        tier.asg_name
        for tier in settings.tiers
        if scaling.find_asg(aws, tier.asg_name) is not None
    ]
    if remaining:
        raise StackError(
            "Auto Scaling Groups are still deleting: "
            + ", ".join(remaining)
            + ". Wait and rerun cleanup."
        )

    print("Deleting the ALB...")
    balancer.delete_load_balancer(aws, settings.alb_name)

    print("Deleting target groups...")
    for tier in settings.tiers:
        from .util import retry_on
        retry_on(
            {"ResourceInUse"},
            lambda: balancer.delete_target_group(aws, tier.tg_name),
            attempts=12,
            delay=10,
            sleep=sleep,
        )

    print("Restoring the app security group and removing the ALB group...")
    vpc_id = network.default_vpc_id(aws)
    alb_sg_id = network.find_security_group(
        aws, settings.alb_sg_name, vpc_id
    )
    network.restore_app_security_group(aws, settings, alb_sg_id)
    if alb_sg_id:
        network.delete_alb_security_group(
            aws, alb_sg_id, sleep=sleep
        )

    print("Deleting launch templates...")
    for tier in settings.tiers:
        delete_launch_template(aws, tier)

    print("Deleting IAM instance profiles and roles...")
    for tier in settings.tiers:
        weather_iam.delete_role_and_profile(aws, tier)

    for filename in ("stack_outputs.env", "stack_outputs.json"):
        (settings.base_dir / filename).unlink(missing_ok=True)

    print("Weather/advisor stack removed.")
    print("Database remains: delete it afterward with delete_database.py.")
    print("Gemini parameter remains until the final cleanup step.")
