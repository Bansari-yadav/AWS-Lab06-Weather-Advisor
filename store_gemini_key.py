"""Store the Gemini key in SSM without printing or saving it locally."""
import getpass
import json
from pathlib import Path
import warnings

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def main():
    """Store a standard SecureString and verify its metadata."""
    settings = {}
    for line in Path(".env").read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            settings[name.strip()] = value.strip().strip("\"'")

    region = settings["AWS_REGION"]
    parameter_name = settings["GEMINI_PARAM_NAME"]
    ssm = boto3.client("ssm", region_name=region)

    warnings.simplefilter("error", getpass.GetPassWarning)
    key = getpass.getpass("Paste Gemini API key (hidden), then press Enter: ").strip()
    if not key:
        raise SystemExit("No key entered. Nothing was stored.")

    try:
        result = ssm.put_parameter(
            Name=parameter_name,
            Value=key,
            Type="SecureString",
            Tier="Standard",
            Overwrite=True,
        )
    finally:
        key = None

    metadata = ssm.describe_parameters(
        ParameterFilters=[
            {"Key": "Name", "Option": "Equals", "Values": [parameter_name]}
        ]
    )["Parameters"]

    if len(metadata) != 1 or metadata[0]["Type"] != "SecureString":
        raise SystemExit("Parameter metadata verification failed.")

    evidence = {
        "Region": region,
        "Name": metadata[0]["Name"],
        "Type": metadata[0]["Type"],
        "Tier": metadata[0]["Tier"],
        "Version": result["Version"],
    }
    Path("evidence").mkdir(exist_ok=True)
    Path("evidence/C3_ssm_parameter_metadata.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2))
    print("Stored and verified. No API key was printed or saved locally.")


if __name__ == "__main__":
    try:
        main()
    except ClientError as error:
        raise SystemExit(f"AWS error: {error.response['Error']['Code']}: {error.response['Error']['Message']}")
    except BotoCoreError as error:
        raise SystemExit(f"AWS connection/configuration error: {type(error).__name__}")
