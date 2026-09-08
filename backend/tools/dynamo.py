"""Shared DynamoDB handle.

Single-table design, one table for everything (build plan §3):

    Episode            PK=EPISODE#{id}        SK=META
    Patient index      PK=PATIENT#{id}        SK=EPISODE#{created_at}#{id}
    Result history     PK=PATIENT#{id}        SK=RESULT#{test_code}#{date}
    Patient profile    PK=PATIENT#{id}        SK=PROFILE
    Idempotency claim  PK=IDEM#{key}          SK=CLAIM
"""

from __future__ import annotations

import os
from functools import lru_cache

import boto3

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
TABLE_NAME = os.environ.get("NANI_TABLE", "nani-ai")


@lru_cache(maxsize=1)
def table():
    """The nani-ai table resource. Cached — boto3 clients are expensive to build."""
    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)


def episode_pk(episode_id: str) -> str:
    return f"EPISODE#{episode_id}"


def patient_pk(patient_id: str) -> str:
    return f"PATIENT#{patient_id}"
