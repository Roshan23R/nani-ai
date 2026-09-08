"""Atomic idempotency claims.

The scheduler can and will fire twice. Every side effect that costs money or
reaches a real person — a booking email, a consult request — must claim its key
here **before** it fires, not after.

This is one conditional write, so there is no check-then-act race:

    put_item(..., ConditionExpression="attribute_not_exists(PK)")

If the condition fails, someone else already claimed it and this caller must do
nothing. That is strictly better than the Firestore read-then-write the original
build used, and it is worth pointing at in the demo.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from botocore.exceptions import ClientError

from tools.dynamo import table

#: Claims expire so the table does not grow forever. Comfortably longer than any
#: episode: a lab report can take days, and a retry must not silently re-send
#: because the claim aged out mid-episode.
CLAIM_TTL_DAYS = 90


def claim_key(episode_id: str, test_code: str, attempt: int = 1) -> str:
    """The idempotency key for one side effect.

    `attempt` exists so a deliberate retry after a genuine failure can claim a
    fresh key, while an accidental double-fire of the same attempt cannot.
    """
    return f"{episode_id}:{test_code}:{attempt}"


@dataclass(frozen=True)
class ClaimResult:
    key: str
    acquired: bool
    #: Set when the claim was already held — when, and by which episode.
    held_since: str | None = None

    def __bool__(self) -> bool:
        return self.acquired


def acquire(key: str, *, episode_id: str, purpose: str = "") -> ClaimResult:
    """Try to claim `key`. Returns falsy if someone already holds it.

    Call this immediately before the side effect:

        if not acquire(k, episode_id=eid, purpose="booking_email"):
            return                      # already sent, do nothing
        send_the_email()
    """
    now = datetime.now(timezone.utc)
    try:
        table().put_item(
            Item={
                "PK": f"IDEM#{key}",
                "SK": "CLAIM",
                "episode_id": episode_id,
                "purpose": purpose,
                "claimed_at": now.isoformat().replace("+00:00", "Z"),
                "expires_at": int(time.time()) + CLAIM_TTL_DAYS * 86400,
            },
            ConditionExpression="attribute_not_exists(PK)",
        )
        return ClaimResult(key=key, acquired=True)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return ClaimResult(key=key, acquired=False, held_since=_held_since(key))


def _held_since(key: str) -> str | None:
    item = table().get_item(Key={"PK": f"IDEM#{key}", "SK": "CLAIM"}).get("Item")
    return item.get("claimed_at") if item else None


def is_claimed(key: str) -> bool:
    """Has this side effect already happened?"""
    return "Item" in table().get_item(Key={"PK": f"IDEM#{key}", "SK": "CLAIM"})


def release(key: str) -> None:
    """Give a claim back.

    Only for a side effect that **definitely** did not happen — the SES call
    raised before sending, say. Never release on an ambiguous failure: a
    duplicate booking email is worse than a missing one, so when in doubt keep
    the claim and let a human retry with a fresh attempt number.
    """
    table().delete_item(Key={"PK": f"IDEM#{key}", "SK": "CLAIM"})
