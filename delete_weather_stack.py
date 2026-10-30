"""Delete the weather/advisor stack using Python and boto3."""
import logging

from botocore.exceptions import BotoCoreError, ClientError, WaiterError

from stack.clients import AwsClients
from stack.config import ConfigError
from stack.network import StackError
from stack.weather_config import WeatherSettings
from stack.weather_runner import delete_weather_stack


def main():
    """Load settings and remove the application infrastructure."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = WeatherSettings.from_file()
    aws = AwsClients.create(settings.region)
    delete_weather_stack(aws, settings)


if __name__ == "__main__":
    try:
        main()
    except ClientError as error:
        print("AWS operation:", error.operation_name)
        print("AWS error code:", error.response["Error"]["Code"])
        raise SystemExit(1)
    except WaiterError:
        raise SystemExit(
            "AWS deletion did not finish within the waiting period. "
            "Inspect its status before retrying."
        )
    except (ConfigError, StackError, ValueError) as error:
        raise SystemExit(str(error))
    except BotoCoreError as error:
        raise SystemExit(
            "AWS connection/configuration error: " + type(error).__name__
        )
