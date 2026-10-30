"""IAM policy documents as Python dictionaries."""
from __future__ import annotations

OBJECT_KEY = "shared.txt"


def trust_policy() -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }


def uploader_policy(bucket: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["s3:PutObject"],
            "Resource": f"arn:aws:s3:::{bucket}/{OBJECT_KEY}",
        }],
    }


def viewer_policy(bucket: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": f"arn:aws:s3:::{bucket}/{OBJECT_KEY}",
            },
            {
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": f"arn:aws:s3:::{bucket}",
            },
        ],
    }


def policy_for(tier_name: str, bucket: str) -> dict:
    return {
        "uploader": uploader_policy,
        "viewer": viewer_policy,
    }[tier_name](bucket)