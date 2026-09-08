"""Booking and consult emails via Amazon SES.

SES is in sandbox: **1 email/second, 200/day, verified recipients only.** A
four-test prescription sends four emails in a loop, so the throttle here is not
optional — without it the third send throws and the episode escalates for no
good reason.

The caller must already hold the idempotency claim. This module does not check;
it just sends. Claiming is the coordinator's job and happens first.
"""

from __future__ import annotations

import logging
import threading
import time

import boto3
from botocore.exceptions import ClientError

from tools.config import (
    AWS_REGION,
    DRY_RUN,
    SES_DOCTOR_RECIPIENT,
    SES_LAB_RECIPIENT,
    SES_SEND_INTERVAL,
    SES_SENDER,
)

log = logging.getLogger(__name__)

_client = None
_lock = threading.Lock()
_last_send = 0.0


def client():
    global _client
    if _client is None:
        _client = boto3.client("ses", region_name=AWS_REGION)
    return _client


def _throttle() -> None:
    """Hold the global send rate under one per second."""
    global _last_send
    with _lock:
        wait = SES_SEND_INTERVAL - (time.monotonic() - _last_send)
        if wait > 0:
            time.sleep(wait)
        _last_send = time.monotonic()


def send(*, to: str, subject: str, body: str) -> str:
    """Send one plain-text email. Returns the SES message id."""
    if DRY_RUN:
        log.info("DRY RUN, not sending to %s: %s", to, subject)
        return f"dry-run-{int(time.time() * 1000)}"

    _throttle()
    try:
        resp = client().send_email(
            Source=SES_SENDER,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        return resp["MessageId"]
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "MessageRejected":
            log.error(
                "SES rejected %s — in sandbox the recipient must be verified first", to
            )
        raise


def booking_request(*, lab: dict, test: dict, episode: dict, slot: str | None = None) -> str:
    """Ask a lab to book one test."""
    patient_ref = episode["episode_id"]
    when = f"\nPreferred slot: {slot}\n" if slot else "\n"
    body = (
        f"Hello {lab.get('name', 'there')},\n\n"
        f"I would like to book the following test:\n\n"
        f"  {test.get('display_name')}  ({test.get('urgency', 'routine')})\n"
        f"{when}"
        f"Please reply to confirm availability and cost.\n\n"
        f"Reference: {patient_ref}\n\n"
        f"Sent by Nani AI on behalf of the patient.\n"
        f"This is an automated booking request from a hackathon demo project.\n"
    )
    return send(
        to=SES_LAB_RECIPIENT,
        subject=f"Test booking request — {test.get('display_name')} [{patient_ref}]",
        body=body,
    )


def consult_request(*, episode: dict, analysis: dict, slot: str) -> str:
    """Ask the doctor for a follow-up, with what changed and why."""
    doctor = (episode.get("prescription") or {}).get("doctor") or "Doctor"
    findings = "\n".join(f"  - {f}" for f in analysis.get("findings", []))
    body = (
        f"Dear {doctor},\n\n"
        f"A follow-up consultation is requested for reference {episode['episode_id']}.\n\n"
        f"What changed:\n{findings}\n\n"
        f"Proposed slot: {slot}\n\n"
        f"{analysis.get('disclaimer', '')}\n\n"
        f"Sent by Nani AI on behalf of the patient.\n"
    )
    return send(
        to=SES_DOCTOR_RECIPIENT,
        subject=f"Follow-up consultation request [{episode['episode_id']}]",
        body=body,
    )
