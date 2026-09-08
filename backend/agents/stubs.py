"""Canned stand-ins for logistics and diagnostics.

Build order rule: get the whole path running badly first, then deepen. These
satisfy the same interface the real agents will, so swapping one in is a
constructor argument, not a rewrite.

Nothing here calls a third-party API, sends email, or costs money — which also
makes them what the tests run against.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

_LABS = [
    {
        "place_id": "stub-suraksha-saltlake",
        "name": "Suraksha Diagnostics, Salt Lake",
        "address": "DD-27, Sector 1, Salt Lake, Kolkata 700064",
        "rating": 4.3,
        "distance_km": 2.1,
        "open_now": True,
    },
    {
        "place_id": "stub-dr-lal-gariahat",
        "name": "Dr Lal PathLabs, Gariahat",
        "address": "Gariahat Road, Ballygunge, Kolkata 700019",
        "rating": 4.1,
        "distance_km": 3.8,
        "open_now": True,
    },
    {
        "place_id": "stub-thyrocare-newtown",
        "name": "Thyrocare Collection Centre, New Town",
        "address": "Action Area I, New Town, Kolkata 700156",
        "rating": 3.9,
        "distance_km": 6.4,
        "open_now": False,
    },
]


class StubLogistics:
    """Finds fake labs, sends no email, holds no slot."""

    name = "logistics(stub)"

    def find_labs(self, *, city: str, tests: list[dict]) -> list[dict]:
        labs = [dict(lab) for lab in _LABS]
        chosen = next((l for l in labs if l["open_now"]), labs[0])
        chosen["selected"] = True
        chosen["selection_reason"] = (
            f"Closest centre open today offering all {len(tests)} tests"
        )
        for lab in labs:
            lab.setdefault("selected", False)
            lab.setdefault("selection_reason", None)
        return labs

    def send_booking_request(self, *, lab: dict, test: dict, episode: dict) -> str:
        return f"stub-message-{episode['episode_id']}-{test['test_code']}"

    def hold_slot(self, *, lab: dict, test: dict) -> str:
        slot = datetime.now(timezone.utc).replace(
            hour=8, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        return slot.isoformat().replace("+00:00", "Z")

    def request_consult(self, *, episode: dict) -> dict:
        slot = datetime.now(timezone.utc).replace(
            hour=17, minute=0, second=0, microsecond=0
        ) + timedelta(days=2)
        doctor = (episode.get("prescription") or {}).get("doctor") or "your doctor"
        return {
            "requested_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "doctor": doctor,
            "proposed_slot": slot.isoformat().replace("+00:00", "Z"),
            "status": "requested",
        }


class StubDiagnostics:
    """Returns a fixed falling-haemoglobin report — the shape the UI expects."""

    name = "diagnostics(stub)"

    def read_report(self, *, file_bytes: bytes, filename: str) -> list[dict]:
        return [
            {
                "test_code": "HB",
                "display_name": "Haemoglobin",
                "value": 9.8,
                "unit": "g/dL",
                "ref_low": 12.0,
                "ref_high": 15.0,
            }
        ]

    def assess(self, *, values: list[dict], history: dict) -> dict:
        low = [v for v in values if v.get("flag") == "low"]
        if low:
            names = ", ".join(v["display_name"] for v in low)
            return {
                "severity": "attention",
                "consult_needed": True,
                "findings": [f"{names} is below the reference range printed on the report."],
                "patient_summary": (
                    f"Your {names.lower()} is below the normal range. "
                    "This is worth discussing with your doctor."
                ),
                "disclaimer": "This is not medical advice. A doctor should review these results.",
            }
        return {
            "severity": "normal",
            "consult_needed": False,
            "findings": ["All values sit within the reference ranges printed on the report."],
            "patient_summary": "Everything on this report looks to be within the normal range.",
            "disclaimer": "This is not medical advice. A doctor should review these results.",
        }
