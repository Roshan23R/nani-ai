"""Episode persistence, shaped exactly like the frozen API contract.

The dict this module stores and returns **is** the Episode object the frontend
consumes (`client/api-contract.md` §3). There is no separate internal model and
no mapping layer — one shape, so a field cannot drift between the database and
the API response.

Two things DynamoDB forces on us:
  * floats must go in as Decimal and come back out as float
  * empty top-level attributes are fine, but None must be written explicitly so
    the contract's nullability rules survive a round trip
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key

from state.machine import State, assert_legal, coerce
from tools.dynamo import episode_pk, patient_pk, table

ACTORS = frozenset(
    {"patient", "intake_agent", "logistics_agent", "diagnostics_agent", "scheduler"}
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_episode_id() -> str:
    return f"ep_{secrets.token_hex(3)}"


# --- DynamoDB type plumbing ------------------------------------------------

def _encode(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_encode(v) for v in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


# --- episodes --------------------------------------------------------------

def new_episode(patient_id: str, *, upload_name: str | None = None) -> dict:
    """A fresh episode in PRESCRIPTION_RECEIVED, contract-shaped.

    Every nullable field is present and null rather than absent — the frontend
    codes defensively against nulls, not against missing keys.
    """
    ts = now_iso()
    return {
        "episode_id": new_episode_id(),
        "patient_id": patient_id,
        "state": State.PRESCRIPTION_RECEIVED.value,
        "created_at": ts,
        "updated_at": ts,
        "summary_line": "Reading your prescription",
        "prescription": None,
        "confirmation": None,
        "labs": [],
        "bookings": [],
        "report": None,
        "analysis": None,
        "consultation": None,
        "timeline": [
            {
                "at": ts,
                "actor": "patient",
                "action": "uploaded_prescription",
                "detail": upload_name or "prescription uploaded",
            }
        ],
        "error": None,
    }


def add_timeline(episode: dict, actor: str, action: str, detail: str = "") -> dict:
    """Append a timeline entry. Mutates and returns the episode."""
    if actor not in ACTORS:
        raise ValueError(f"Unknown timeline actor {actor!r}. Allowed: {sorted(ACTORS)}")
    episode.setdefault("timeline", []).append(
        {"at": now_iso(), "actor": actor, "action": action, "detail": detail}
    )
    episode["updated_at"] = now_iso()
    return episode


def apply_transition(
    episode: dict,
    to: State | str,
    *,
    actor: str,
    action: str,
    detail: str = "",
    summary_line: str | None = None,
) -> dict:
    """Move an episode to a new state, validated, with a timeline entry.

    State changes and timeline entries happen together, in one function, so a
    silent state change is not expressible. Raises IllegalTransition if the
    move is not permitted.
    """
    target = assert_legal(episode["state"], to)
    episode["state"] = target.value
    if summary_line is not None:
        episode["summary_line"] = summary_line
    return add_timeline(episode, actor, action, detail)


def set_error(
    episode: dict, code: str, message: str, action_hint: str = "", retryable: bool = True
) -> dict:
    """Populate the contract's error object. Only meaningful in NEEDS_HUMAN."""
    episode["error"] = {
        "code": code,
        "message": message,
        "action_hint": action_hint,
        "retryable": retryable,
    }
    return episode


def put_episode(episode: dict) -> dict:
    """Write the episode and its patient index entry."""
    episode["updated_at"] = now_iso()
    eid, pid = episode["episode_id"], episode["patient_id"]

    table().put_item(Item=_encode({**episode, "PK": episode_pk(eid), "SK": "META"}))
    table().put_item(
        Item={
            "PK": patient_pk(pid),
            "SK": f"EPISODE#{episode['created_at']}#{eid}",
            "episode_id": eid,
            "state": episode["state"],
            "summary_line": episode.get("summary_line", ""),
            "created_at": episode["created_at"],
            "updated_at": episode["updated_at"],
        }
    )
    return episode


def get_episode(episode_id: str) -> dict | None:
    item = table().get_item(Key={"PK": episode_pk(episode_id), "SK": "META"}).get("Item")
    if not item:
        return None
    return _strip_keys(_decode(item))


def list_episodes(patient_id: str, limit: int = 20) -> list[dict]:
    """Episode summaries for a patient, newest first."""
    resp = table().query(
        KeyConditionExpression=Key("PK").eq(patient_pk(patient_id))
        & Key("SK").begins_with("EPISODE#"),
        ScanIndexForward=False,
        Limit=limit,
    )
    return [_strip_keys(_decode(i)) for i in resp.get("Items", [])]


def _strip_keys(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in ("PK", "SK")}


# --- patients --------------------------------------------------------------

def put_patient(profile: dict) -> dict:
    table().put_item(
        Item=_encode({**profile, "PK": patient_pk(profile["patient_id"]), "SK": "PROFILE"})
    )
    return profile


def get_patient(patient_id: str) -> dict | None:
    item = table().get_item(Key={"PK": patient_pk(patient_id), "SK": "PROFILE"}).get("Item")
    return _strip_keys(_decode(item)) if item else None


def list_patients() -> list[dict]:
    """Patient PROFILE rows. A scan is fine — there are a handful of demo + Google users."""
    resp = table().scan(FilterExpression=Key("SK").eq("PROFILE"))
    return [_strip_keys(_decode(i)) for i in resp.get("Items", [])]


# --- result history (what the trend comparison reads) ----------------------

def put_result(patient_id: str, test_code: str, date: str, value: Any, unit: str = "") -> None:
    table().put_item(
        Item=_encode(
            {
                "PK": patient_pk(patient_id),
                "SK": f"RESULT#{test_code}#{date}",
                "test_code": test_code,
                "date": date,
                "value": value,
                "unit": unit,
            }
        )
    )


def get_history(patient_id: str, test_code: str) -> list[dict]:
    """Prior readings for one test, oldest first — the shape `value.history` wants."""
    resp = table().query(
        KeyConditionExpression=Key("PK").eq(patient_pk(patient_id))
        & Key("SK").begins_with(f"RESULT#{test_code}#"),
        ScanIndexForward=True,
    )
    return [
        {"date": _decode(i["date"]), "value": _decode(i["value"])}
        for i in resp.get("Items", [])
    ]
