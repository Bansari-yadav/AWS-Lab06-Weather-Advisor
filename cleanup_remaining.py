import json
from pathlib import Path

from botocore.exceptions import ClientError
from stack.clients import AwsClients
from stack.weather_config import WeatherSettings

settings = WeatherSettings.from_file()
aws = AwsClients.create(settings.region)

try:
    aws.ssm.delete_parameter(Name=settings.gemini_param_name)
    print("Gemini SSM parameter deleted.")
except ClientError as error:
    if error.response["Error"]["Code"] == "ParameterNotFound":
        print("Gemini SSM parameter already absent.")
    else:
        print("GEMINI PARAMETER CLEANUP ERROR:")
        print(error.response["Error"]["Message"])

rule_file = Path("evidence/browser_ssh_rule.json")
if rule_file.exists():
    saved = json.loads(rule_file.read_text(encoding="utf-8"))
    try:
        aws.ec2.revoke_security_group_ingress(
            GroupId=saved["GroupId"],
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "PrefixListIds": [{
                    "PrefixListId": saved["PrefixListId"]
                }],
            }],
        )
        print("Temporary browser SSH rule removed.")
    except ClientError as error:
        if error.response["Error"]["Code"] == "InvalidPermission.NotFound":
            print("Temporary browser SSH rule already absent.")
        else:
            print("SSH RULE CLEANUP ERROR:")
            print(error.response["Error"]["Message"])
