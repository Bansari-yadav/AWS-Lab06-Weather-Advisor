"""Create the weather lab database using the shared stack package."""
from botocore.exceptions import BotoCoreError, ClientError, WaiterError

from stack.clients import AwsClients
from stack.config import ConfigError
from stack.database import create_database
from stack.network import StackError
from stack.weather_config import WeatherSettings


def main():
    """Load configuration and create the database."""
    settings = WeatherSettings.from_file()
    aws = AwsClients.create(settings.region)
    create_database(aws, settings)


if __name__ == "__main__":
    try:
        main()
    except ClientError as error:
        print("AWS operation:", error.operation_name)
        print("AWS error code:", error.response["Error"]["Code"])
        raise SystemExit(1)
    except WaiterError:
        raise SystemExit(
            "Database wait did not finish successfully. "
            "Inspect its status before retrying."
        )
    except (ConfigError, StackError) as error:
        raise SystemExit(str(error))
    except BotoCoreError as error:
        raise SystemExit(
            "AWS connection/configuration error: " + type(error).__name__
        )
