"""Slot holds via Google Calendar.

Kept on Google because AWS has no calendar service at all — this is the one
third-party dependency with no alternative. Uses the OAuth refresh-token flow
over plain HTTP so it needs no extra SDK.

Falls back to a computed slot when no credentials are configured. The episode
still records a slot_hold and the demo still reads correctly; only the real
calendar entry is missing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from tools.config import (
    GOOGLE_CALENDAR_ID,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REFRESH_TOKEN,
    has_calendar,
)

log = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{cal}/events"


def _next_morning(days_ahead: int = 1) -> datetime:
    return (datetime.now(timezone.utc) + timedelta(days=days_ahead)).replace(
        hour=8, minute=0, second=0, microsecond=0
    )


def _access_token() -> str:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def hold_slot(*, lab: dict, test: dict, days_ahead: int = 1) -> str:
    """Put a one-hour hold on the calendar. Returns the slot as an ISO string."""
    start = _next_morning(days_ahead)
    end = start + timedelta(hours=1)
    iso = start.isoformat().replace("+00:00", "Z")

    if not has_calendar():
        log.warning("Google Calendar not configured — recording the slot without a hold")
        return iso

    try:
        token = _access_token()
        httpx.post(
            EVENTS_URL.format(cal=GOOGLE_CALENDAR_ID),
            headers={"Authorization": f"Bearer {token}"},
            json={
                "summary": f"{test.get('display_name')} — {lab.get('name')}",
                "description": (
                    "Provisional hold placed by Nani AI pending lab confirmation."
                ),
                "location": lab.get("address", ""),
                "start": {"dateTime": iso},
                "end": {"dateTime": end.isoformat().replace("+00:00", "Z")},
            },
            timeout=10.0,
        ).raise_for_status()
    except Exception as exc:  # noqa: BLE001 — a failed hold must not end an episode
        log.warning("Calendar hold failed (%s) — recording the slot anyway", exc)
    return iso
