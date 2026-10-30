"""Verify the lab resources are absent after cleanup."""
import json
from pathlib import Path

from botocore.exceptions import ClientError
from stack.clients import AwsClients
from stack.weather_config import WeatherSettings

settings = WeatherSettings.from_file()
aws = AwsClients.create(settings.region)
report = {}


def verify(label, client, operation, collection, match_key, names,
           output_key=None):
    """List matching lab resources using every available result page."""
    try:
        if client.can_paginate(operation):
            pages = client.get_paginator(operation).paginate()
        else:
            pages = [getattr(client, operation)()]
        report[label] = [
            item[output_key or match_key]
            for page in pages
            for item in page[collection]
            if item.get(match_key) in names
        ]
    except ClientError as error:
        report[label] = {
            "verification_error": error.response["Error"]["Message"]
        }


verify("DatabaseInstances", aws.rds, "describe_db_instances",
       "DBInstances", "DBInstanceIdentifier", [settings.db_instance_id])
verify("DatabaseSnapshots", aws.rds, "describe_db_snapshots",
       "DBSnapshots", "DBInstanceIdentifier", [settings.db_instance_id],
       "DBSnapshotIdentifier")
verify("AutomatedBackups", aws.rds,
       "describe_db_instance_automated_backups",
       "DBInstanceAutomatedBackups", "DBInstanceIdentifier",
       [settings.db_instance_id])
verify("DatabaseSubnetGroups", aws.rds, "describe_db_subnet_groups",
       "DBSubnetGroups", "DBSubnetGroupName",
       [settings.db_subnet_group_name])
verify("LoadBalancers", aws.elbv2, "describe_load_balancers",
       "LoadBalancers", "LoadBalancerName", [settings.alb_name])
verify("TargetGroups", aws.elbv2, "describe_target_groups",
       "TargetGroups", "TargetGroupName",
       [tier.tg_name for tier in settings.tiers])
verify("AutoScalingGroups", aws.autoscaling,
       "describe_auto_scaling_groups", "AutoScalingGroups",
       "AutoScalingGroupName", [tier.asg_name for tier in settings.tiers])
verify("LaunchTemplates", aws.ec2, "describe_launch_templates",
       "LaunchTemplates", "LaunchTemplateName",
       [tier.lt_name for tier in settings.tiers])
verify("LabRoles", aws.iam, "list_roles", "Roles", "RoleName",
       [tier.role_name for tier in settings.tiers])
verify("InstanceProfiles", aws.iam, "list_instance_profiles",
       "InstanceProfiles", "InstanceProfileName",
       [tier.profile_name for tier in settings.tiers])
verify("SecretParameters", aws.ssm, "describe_parameters",
       "Parameters", "Name",
       [settings.db_password_param, settings.gemini_param_name])
verify("LabSecurityGroups", aws.ec2, "describe_security_groups",
       "SecurityGroups", "GroupName",
       [settings.db_sg_name, settings.alb_sg_name])

try:
    instances = []
    for page in aws.ec2.get_paginator("describe_instances").paginate(
        Filters=[
            {"Name": "tag:Name", "Values": ["weather-app", "advisor-app"]},
            {"Name": "instance.group-id", "Values": [settings.app_sg_id]},
        ]
    ):
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                if instance["State"]["Name"] != "terminated":
                    instances.append({
                        "Id": instance["InstanceId"],
                        "State": instance["State"]["Name"],
                    })
    report["NonterminatedLabInstances"] = instances
except ClientError as error:
    report["NonterminatedLabInstances"] = {
        "verification_error": error.response["Error"]["Message"]
    }

rule_file = Path("evidence/browser_ssh_rule.json")
if rule_file.exists():
    saved = json.loads(rule_file.read_text())
    try:
        group = aws.ec2.describe_security_groups(
            GroupIds=[saved["GroupId"]]
        )["SecurityGroups"][0]
        report["TemporaryBrowserSSHRule"] = [
            rule for rule in group["IpPermissions"]
            if rule.get("FromPort") == 22
            and any(
                source["PrefixListId"] == saved["PrefixListId"]
                for source in rule.get("PrefixListIds", [])
            )
        ]
    except ClientError as error:
        report["TemporaryBrowserSSHRule"] = {
            "verification_error": error.response["Error"]["Message"]
        }

Path("evidence/H10_final_verification.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
for label, value in report.items():
    print(f"{label}: {json.dumps(value)}")

if all(value == [] for value in report.values()):
    print("\nVERIFIED: all listed lab resources are absent.")
else:
    raise SystemExit(
        "Cleanup verification is incomplete. Send the output."
    )
