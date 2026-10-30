"""Create the weather/advisor stack using Python and boto3."""
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError, WaiterError

from stack.clients import AwsClients
from stack.config import ConfigError
from stack.network import StackError
from stack.weather_config import WeatherSettings
from stack.weather_runner import create_weather_stack


def main():
    """Load settings, identify the AWS account, and build both tiers."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = WeatherSettings.from_file()
    aws = AwsClients.create(settings.region)
    account_id = boto3.client(
        "sts", region_name=settings.region
    ).get_caller_identity()["Account"]

    create_weather_stack(aws, settings, account_id)


if __name__ == "__main__":
    try:
        main()
    except ClientError as error:
        print("AWS operation:", error.operation_name)
        print("AWS error code:", error.response["Error"]["Code"])
        raise SystemExit(1)
    except WaiterError:
        raise SystemExit(
            "An AWS resource did not become ready within the waiting period. "
            "Inspect its status before retrying."
        )
    except (ConfigError, StackError, ValueError) as error:
        raise SystemExit(str(error))
    except BotoCoreError as error:
        raise SystemExit(
            "AWS connection/configuration error: " + type(error).__name__
        )
