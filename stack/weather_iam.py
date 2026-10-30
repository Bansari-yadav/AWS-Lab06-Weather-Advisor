"""IAM roles and instance profiles for the weather lab."""
import json

from botocore.exceptions import ClientError

from .network import StackError
from .policies import trust_policy
from .util import error_code, ignore_errors
from .weather_policies import secret_policy


def ensure_role_and_profile(aws, settings, tier, account_id):
    """Ensure a tier has an EC2 role, its own secret policy, and a profile."""
    with ignore_errors("EntityAlreadyExists"):
        aws.iam.create_role(
            RoleName=tier.role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy()),
        )

    role = aws.iam.get_role(RoleName=tier.role_name)["Role"]
    if role["AssumeRolePolicyDocument"] != trust_policy():
        raise StackError(
            f"Existing role {tier.role_name} has an unexpected trust policy."
        )

    wanted_policy = secret_policy(settings, tier, account_id)
    existing_policy = None
    try:
        existing_policy = aws.iam.get_role_policy(
            RoleName=tier.role_name,
            PolicyName=tier.policy_name,
        )["PolicyDocument"]
    except ClientError as error:
        if error_code(error) != "NoSuchEntity":
            raise

    if existing_policy != wanted_policy:
        aws.iam.put_role_policy(
            RoleName=tier.role_name,
            PolicyName=tier.policy_name,
            PolicyDocument=json.dumps(wanted_policy),
        )

    inline_names = aws.iam.list_role_policies(
        RoleName=tier.role_name
    )["PolicyNames"]
    attached = aws.iam.list_attached_role_policies(
        RoleName=tier.role_name
    )["AttachedPolicies"]
    if set(inline_names) != {tier.policy_name} or attached:
        raise StackError(
            f"Role {tier.role_name} has additional policies. "
            "Review them before continuing."
        )

    with ignore_errors("EntityAlreadyExists"):
        aws.iam.create_instance_profile(
            InstanceProfileName=tier.profile_name
        )

    profile = aws.iam.get_instance_profile(
        InstanceProfileName=tier.profile_name
    )["InstanceProfile"]
    role_names = {role["RoleName"] for role in profile["Roles"]}

    if role_names and role_names != {tier.role_name}:
        raise StackError(
            f"Profile {tier.profile_name} contains an unexpected role."
        )
    if not role_names:
        aws.iam.add_role_to_instance_profile(
            InstanceProfileName=tier.profile_name,
            RoleName=tier.role_name,
        )


def delete_role_and_profile(aws, tier):
    """Remove this lab's profile, inline policy, and role if present."""
    with ignore_errors("NoSuchEntity"):
        aws.iam.remove_role_from_instance_profile(
            InstanceProfileName=tier.profile_name,
            RoleName=tier.role_name,
        )

    with ignore_errors("NoSuchEntity"):
        aws.iam.delete_instance_profile(
            InstanceProfileName=tier.profile_name
        )

    with ignore_errors("NoSuchEntity"):
        aws.iam.delete_role_policy(
            RoleName=tier.role_name,
            PolicyName=tier.policy_name,
        )

    with ignore_errors("NoSuchEntity"):
        aws.iam.delete_role(RoleName=tier.role_name)
