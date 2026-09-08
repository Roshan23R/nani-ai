"""Nearby diagnostic labs, via Google Places.

Staying on Google deliberately. Amazon Location Service exists and would be a
neater AWS story, but its India POI coverage for small pathology labs and
collection centres is thin, and a lab search over Kolkata that returns three
irrelevant hospitals breaks the demo in the most visible way possible.
Third-party APIs are explicitly permitted.

Falls back to a canned Kolkata list when no API key is configured, so the
cascade always runs.
"""

from __future__ import annotations

import logging

import httpx

from tools.config import GOOGLE_PLACES_API_KEY, has_places

log = logging.getLogger(__name__)

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELDS = (
    "places.id,places.displayName,places.formattedAddress,places.rating,"
    "places.currentOpeningHours.openNow,places.location"
)

_FALLBACK = [
    {
        "place_id": "fallback-suraksha-saltlake",
        "name": "Suraksha Diagnostics, Salt Lake",
        "address": "DD-27, Sector 1, Salt Lake, Kolkata 700064",
        "rating": 4.3,
        "distance_km": 2.1,
        "open_now": True,
    },
    {
        "place_id": "fallback-dr-lal-gariahat",
        "name": "Dr Lal PathLabs, Gariahat",
        "address": "Gariahat Road, Ballygunge, Kolkata 700019",
        "rating": 4.1,
        "distance_km": 3.8,
        "open_now": True,
    },
    {
        "place_id": "fallback-thyrocare-newtown",
        "name": "Thyrocare Collection Centre, New Town",
        "address": "Action Area I, New Town, Kolkata 700156",
        "rating": 3.9,
        "distance_km": 6.4,
        "open_now": False,
    },
]


def find_labs(city: str = "Kolkata", limit: int = 5) -> list[dict]:
    """Diagnostic labs near `city`, best-rated first."""
    if not has_places():
        log.warning("GOOGLE_PLACES_API_KEY not set — using the canned lab list")
        return [dict(lab) for lab in _FALLBACK[:limit]]

    try:
        resp = httpx.post(
            ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
                "X-Goog-FieldMask": FIELDS,
            },
            json={
                "textQuery": f"diagnostic pathology lab in {city}",
                "maxResultCount": limit,
                "languageCode": "en",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        places = resp.json().get("places", [])
    except Exception as exc:  # noqa: BLE001 — a lab search must never end an episode
        log.warning("Places lookup failed (%s) — using the canned list", exc)
        return [dict(lab) for lab in _FALLBACK[:limit]]

    labs = [
        {
            "place_id": p.get("id", ""),
            "name": (p.get("displayName") or {}).get("text", "Unnamed centre"),
            "address": p.get("formattedAddress", ""),
            "rating": float(p["rating"]) if p.get("rating") is not None else None,
            "distance_km": None,  # Places text search does not return distance
            "open_now": (p.get("currentOpeningHours") or {}).get("openNow"),
        }
        for p in places
    ]
    return labs or [dict(lab) for lab in _FALLBACK[:limit]]


def select_lab(labs: list[dict], tests: list[dict]) -> list[dict]:
    """Mark one lab selected, with a reason the timeline can show.

    Deterministic: open now beats closed, then rating. Choosing a lab is not a
    judgement call worth an LLM round trip.
    """
    if not labs:
        return labs
    ranked = sorted(
        labs,
        key=lambda l: (l.get("open_now") is not True, -(l.get("rating") or 0)),
    )
    chosen = ranked[0]
    for lab in labs:
        lab["selected"] = lab is chosen
        lab["selection_reason"] = (
            f"{'Open now, ' if chosen.get('open_now') else ''}"
            f"best rated of {len(labs)} nearby centres for all {len(tests)} tests"
            if lab is chosen
            else None
        )
    return labs
