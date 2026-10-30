"""RDS database helpers for the weather lab."""
from __future__ import annotations

from .clients import AwsClients
from .network import (
    StackError,
    default_vpc_id,
    find_security_group,
    subnet_in_az,
)
from .util import error_code, ignore_errors
from .weather_config import WeatherSettings
from botocore.exceptions import ClientError


def database_network(
    aws: AwsClients, settings: WeatherSettings
) -> tuple[str, str, str]:
    """Find the default VPC and subnets, and validate the app group."""
    vpc_id = default_vpc_id(aws)
    subnet_a = subnet_in_az(aws, vpc_id, settings.az_a)
    subnet_b = subnet_in_az(aws, vpc_id, settings.az_b)

    groups = aws.ec2.describe_security_groups(
        GroupIds=[settings.app_sg_id]
    )["SecurityGroups"]
    if not groups or groups[0]["VpcId"] != vpc_id:
        raise StackError(
            "The app security group must belong to the default VPC."
        )
    return vpc_id, subnet_a, subnet_b


def database_ingress(app_sg_id: str, port: int) -> list[dict]:
    """Allow PostgreSQL only from the app security group, with no CIDR."""
    return [{
        "IpProtocol": "tcp",
        "FromPort": port,
        "ToPort": port,
        "UserIdGroupPairs": [{"GroupId": app_sg_id}],
    }]


def ensure_database_security_group(
    aws: AwsClients, settings: WeatherSettings, vpc_id: str
) -> str:
    """Create the database group if missing and ensure its ingress rule."""
    group_id = find_security_group(aws, settings.db_sg_name, vpc_id)
    if group_id is None:
        group_id = aws.ec2.create_security_group(
            GroupName=settings.db_sg_name,
            Description="PostgreSQL access from the lab app group only",
            VpcId=vpc_id,
        )["GroupId"]

    with ignore_errors("InvalidPermission.Duplicate"):
        aws.ec2.authorize_security_group_ingress(
            GroupId=group_id,
            IpPermissions=database_ingress(settings.app_sg_id, settings.db_port),
        )

    group = aws.ec2.describe_security_groups(
        GroupIds=[group_id]
    )["SecurityGroups"][0]
    for rule in group.get("IpPermissions", []):
        if rule.get("IpRanges") or rule.get("Ipv6Ranges"):
            raise StackError(
                "The database security group contains a CIDR rule. "
                "Review it before continuing."
            )
    return group_id


def ensure_database_subnet_group(
    aws: AwsClients,
    settings: WeatherSettings,
    subnet_a: str,
    subnet_b: str,
) -> None:
    """Create the RDS subnet group or verify its existing subnets."""
    try:
        groups = aws.rds.describe_db_subnet_groups(
            DBSubnetGroupName=settings.db_subnet_group_name
        )["DBSubnetGroups"]
    except ClientError as error:
        if error_code(error) != "DBSubnetGroupNotFoundFault":
            raise
        aws.rds.create_db_subnet_group(
            DBSubnetGroupName=settings.db_subnet_group_name,
            DBSubnetGroupDescription="Weather lab subnets in two zones",
            SubnetIds=[subnet_a, subnet_b],
        )
        return

    existing_subnets = {
        subnet["SubnetIdentifier"]
        for subnet in groups[0]["Subnets"]
    }
    if existing_subnets != {subnet_a, subnet_b}:
        raise StackError(
            "The existing database subnet group does not match "
            "the two configured subnets."
        )


def find_database(aws: AwsClients, settings: WeatherSettings) -> dict | None:
    """Return the database description, or None if it does not exist."""
    try:
        return aws.rds.describe_db_instances(
            DBInstanceIdentifier=settings.db_instance_id
        )["DBInstances"][0]
    except ClientError as error:
        if error_code(error) != "DBInstanceNotFound":
            raise
        return None


def ensure_database_password(
    aws: AwsClients,
    settings: WeatherSettings,
    database_exists: bool,
) -> str:
    """Read the password or generate it once; never print or write it locally."""
    import secrets

    try:
        result = aws.ssm.get_parameter(
            Name=settings.db_password_param,
            WithDecryption=True,
        )
        if result["Parameter"]["Type"] != "SecureString":
            raise StackError("The database password must be a SecureString.")
        return result["Parameter"]["Value"]
    except ClientError as error:
        if error_code(error) != "ParameterNotFound":
            raise

    if database_exists:
        raise StackError(
            "Database exists but its password parameter is missing. "
            "Do not generate a different password for an existing database."
        )

    password = secrets.token_hex(16)
    try:
        aws.ssm.put_parameter(
            Name=settings.db_password_param,
            Value=password,
            Type="SecureString",
            Tier="Standard",
            Overwrite=False,
        )
    except ClientError as error:
        if error_code(error) != "ParameterAlreadyExists":
            raise
        return aws.ssm.get_parameter(
            Name=settings.db_password_param,
            WithDecryption=True,
        )["Parameter"]["Value"]
    return password


def database_create_request(
    settings: WeatherSettings,
    security_group_id: str,
    password: str,
) -> dict:
    """Build the RDS request; callers must never log this secret-bearing dict."""
    return {
        "DBInstanceIdentifier": settings.db_instance_id,
        "DBInstanceClass": settings.db_instance_class,
        "Engine": "postgres",
        "AllocatedStorage": 20,
        "StorageType": "gp2",
        "MasterUsername": settings.db_user,
        "MasterUserPassword": password,
        "DBName": settings.db_name,
        "Port": settings.db_port,
        "DBSubnetGroupName": settings.db_subnet_group_name,
        "VpcSecurityGroupIds": [security_group_id],
        "AvailabilityZone": settings.az_a,
        "BackupRetentionPeriod": 0,
        "MultiAZ": False,
        "PubliclyAccessible": False,
        "AutoMinorVersionUpgrade": False,
        "DeletionProtection": False,
        "StorageEncrypted": True,
    }


def validate_database(
    instance: dict,
    settings: WeatherSettings,
    security_group_id: str,
) -> None:
    """Refuse to reuse a database with unexpected configuration."""
    expected = {
        "DBInstanceClass": settings.db_instance_class,
        "Engine": "postgres",
        "AllocatedStorage": 20,
        "StorageType": "gp2",
        "MasterUsername": settings.db_user,
        "DBName": settings.db_name,
        "AvailabilityZone": settings.az_a,
        "BackupRetentionPeriod": 0,
        "MultiAZ": False,
        "PubliclyAccessible": False,
        "DeletionProtection": False,
        "StorageEncrypted": True,
    }
    mismatches = [
        key for key, value in expected.items()
        if instance.get(key) != value
    ]

    actual_groups = {
        group["VpcSecurityGroupId"]
        for group in instance.get("VpcSecurityGroups", [])
    }
    if actual_groups != {security_group_id}:
        mismatches.append("VpcSecurityGroups")

    actual_subnet_group = instance.get(
        "DBSubnetGroup", {}
    ).get("DBSubnetGroupName")
    if actual_subnet_group != settings.db_subnet_group_name:
        mismatches.append("DBSubnetGroupName")

    if mismatches:
        raise StackError(
            "Database configuration differs from the lab: "
            + ", ".join(mismatches)
        )


def create_database(
    aws: AwsClients, settings: WeatherSettings
) -> dict[str, str]:
    """Create or reuse the lab database and save nonsecret outputs."""
    from pathlib import Path

    existing = find_database(aws, settings)
    if existing and existing["DBInstanceStatus"] not in {"creating", "available"}:
        raise StackError(
            "Database is in state "
            + existing["DBInstanceStatus"]
            + "; wait or resolve that state before continuing."
        )

    print("Checking the VPC, subnets, and app security group...")
    vpc_id, subnet_a, subnet_b = database_network(aws, settings)

    print("Ensuring the database security group...")
    group_id = ensure_database_security_group(aws, settings, vpc_id)

    print("Ensuring the database subnet group...")
    ensure_database_subnet_group(aws, settings, subnet_a, subnet_b)

    if existing:
        validate_database(existing, settings, group_id)

    print("Ensuring the password exists in SSM; its value is never printed...")
    password = ensure_database_password(
        aws, settings, database_exists=existing is not None
    )

    try:
        if existing is None:
            request = database_create_request(settings, group_id, password)
            try:
                print("Creating private, encrypted PostgreSQL with retention 0...")
                aws.rds.create_db_instance(**request)
            except ClientError as error:
                if error_code(error) != "DBInstanceAlreadyExists":
                    raise
            finally:
                request.pop("MasterUserPassword", None)
        else:
            print("Database already exists; no duplicate will be created.")
    finally:
        password = None

    print("Waiting for the database to become available...")
    aws.rds.get_waiter("db_instance_available").wait(
        DBInstanceIdentifier=settings.db_instance_id
    )

    instance = find_database(aws, settings)
    if instance is None:
        raise StackError("Database was not found after waiting.")
    validate_database(instance, settings, group_id)

    outputs = {
        "DB_HOST": instance["Endpoint"]["Address"],
        "DB_SECURITY_GROUP_ID": group_id,
    }
    output_path = Path(settings.base_dir) / "db_outputs.env"
    output_path.write_text(
        "".join(f"{key}={value}\n" for key, value in outputs.items()),
        encoding="utf-8",
    )

    print("Database available.")
    print("Database endpoint:", outputs["DB_HOST"])
    print("Backups OFF: retention 0; private; single-AZ; encrypted.")
    print("Nonsecret outputs saved to db_outputs.env.")
    return outputs


def delete_database(aws: AwsClients, settings: WeatherSettings) -> None:
    """Delete the database without a snapshot, then remove its dependencies."""
    from .util import retry_on

    instance = find_database(aws, settings)

    if instance is None:
        print("Database already absent.")
    else:
        if instance["DBInstanceStatus"] != "deleting":
            print("Deleting database without a final snapshot or retained backups...")
            try:
                aws.rds.delete_db_instance(
                    DBInstanceIdentifier=settings.db_instance_id,
                    SkipFinalSnapshot=True,
                    DeleteAutomatedBackups=True,
                )
            except ClientError as error:
                if error_code(error) != "DBInstanceNotFound":
                    raise

        print("Waiting for database deletion...")
        aws.rds.get_waiter("db_instance_deleted").wait(
            DBInstanceIdentifier=settings.db_instance_id
        )

    if find_database(aws, settings) is not None:
        raise StackError(
            "Database still exists. Its remaining resources were not removed."
        )

    print("Removing the database subnet group...")
    with ignore_errors("DBSubnetGroupNotFoundFault"):
        retry_on(
            {"InvalidDBSubnetGroupStateFault"},
            lambda: aws.rds.delete_db_subnet_group(
                DBSubnetGroupName=settings.db_subnet_group_name
            ),
            attempts=10,
            delay=15,
        )

    print("Removing the database security group...")
    groups = aws.ec2.describe_security_groups(
        Filters=[{
            "Name": "group-name",
            "Values": [settings.db_sg_name],
        }]
    )["SecurityGroups"]

    if len(groups) > 1:
        raise StackError(
            "Multiple security groups have the database group name. "
            "Review them before deleting."
        )

    if groups:
        with ignore_errors("InvalidGroup.NotFound"):
            retry_on(
                {"DependencyViolation"},
                lambda: aws.ec2.delete_security_group(
                    GroupId=groups[0]["GroupId"]
                ),
                attempts=10,
                delay=15,
            )

    print("Removing the database password parameter...")
    with ignore_errors("ParameterNotFound"):
        aws.ssm.delete_parameter(Name=settings.db_password_param)

    (settings.base_dir / "db_outputs.env").unlink(missing_ok=True)
    print("Database cleanup finished. Verify snapshots and backups separately.")
