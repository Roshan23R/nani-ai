"""S3: prescription uploads and the watched report inbox.

The inbox is the second trigger. A lab drops a report at
`inbox/{episode_id}/...` and the next heartbeat picks it up — nobody presses a
button, which is the difference between an agent and a form.
"""

from __future__ import annotations

import logging

import boto3

from tools.config import AWS_REGION, S3_BUCKET, S3_INBOX_PREFIX, S3_UPLOAD_PREFIX

log = logging.getLogger(__name__)

__all__ = ['S3_BUCKET', 'client', 'put_upload', 'inbox_key', 'deliver_to_inbox', 'find_report', 'presign']

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.client("s3", region_name=AWS_REGION)
    return _client


def put_upload(data: bytes, filename: str, *, episode_id: str = "") -> str:
    """Store a prescription. Returns an s3:// URL for the episode record."""
    key = f"{S3_UPLOAD_PREFIX}{episode_id + '/' if episode_id else ''}{filename}"
    client().put_object(Bucket=S3_BUCKET, Key=key, Body=data)
    return f"s3://{S3_BUCKET}/{key}"


def inbox_key(episode_id: str, filename: str) -> str:
    return f"{S3_INBOX_PREFIX}{episode_id}/{filename}"


def deliver_to_inbox(episode_id: str, data: bytes, filename: str) -> str:
    """Play the part of the lab: drop a report where the heartbeat will find it."""
    key = inbox_key(episode_id, filename)
    client().put_object(Bucket=S3_BUCKET, Key=key, Body=data)
    return f"s3://{S3_BUCKET}/{key}"


def find_report(episode_id: str) -> tuple[bytes, str] | None:
    """Is there a report waiting for this episode? Returns (bytes, filename)."""
    resp = client().list_objects_v2(
        Bucket=S3_BUCKET, Prefix=f"{S3_INBOX_PREFIX}{episode_id}/", MaxKeys=10
    )
    for obj in resp.get("Contents", []):
        key = obj["Key"]
        if key.endswith("/"):
            continue
        body = client().get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()
        return body, key.rsplit("/", 1)[-1]
    return None


def presign(url_or_key: str, *, expires: int = 86400) -> str:
    """A browsable URL for the UI. The bucket stays private."""
    key = url_or_key.split(f"{S3_BUCKET}/", 1)[-1] if url_or_key.startswith("s3://") else url_or_key
    try:
        return client().generate_presigned_url(
            "get_object", Params={"Bucket": S3_BUCKET, "Key": key}, ExpiresIn=expires
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("presign failed for %s: %s", key, exc)
        return url_or_key
