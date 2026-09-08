"""Logistics agent — find a lab, ask it for a slot, chase the consult.

Where the LLM is and is not:

  * **Choosing** a lab from the candidates is judgement about content, and it
    runs as a Strands agent with a `@tool` it calls itself. Worst case it picks
    a slightly worse centre.
  * **Sending** the email and **holding** the slot are deterministic Python.
    An LLM never decides whether to spend a patient's money or contact a real
    person; the coordinator decides that, having already claimed idempotency.

That split is the whole safety argument in miniature, at the level of one agent.
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field
from strands import Agent, tool

from agents.strands_setup import fast_model
from tools import calendar as calendar_tool
from tools import places, ses

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You choose a diagnostic lab for a patient in India.

Call find_nearby_labs to get the candidates. Then pick exactly one.

Prefer, in order:
1. Open now — a closed centre helps nobody today
2. Higher rating
3. Closer, when distance is known

Give a one-sentence reason a patient would find useful. Name the trade-off if
there is one ("higher rated but further away"). Do not invent labs, ratings or
distances: use only what the tool returned."""


class LabChoice(BaseModel):
    place_id: str = Field(description="place_id of the chosen lab, copied exactly")
    reason: str = Field(description="One sentence, patient-facing, on why this one")


@tool
def find_nearby_labs(city: str) -> str:
    """Find diagnostic labs and collection centres near a city.

    Args:
        city: The city to search in, e.g. "Kolkata".

    Returns:
        A JSON list of candidate labs with name, address, rating and open_now.
    """
    return json.dumps(places.find_labs(city=city), ensure_ascii=False)


class LogisticsAgent:
    """The interface the coordinator drives. Same shape as StubLogistics."""

    name = "logistics"

    def __init__(self) -> None:
        self._agent = Agent(
            model=fast_model(temperature=0.0, max_tokens=500),
            system_prompt=SYSTEM_PROMPT,
            tools=[find_nearby_labs],
            callback_handler=None,
        )

    def find_labs(self, *, city: str, tests: list[dict]) -> list[dict]:
        candidates = places.find_labs(city=city)
        if not candidates:
            return []

        names = ", ".join(t.get("display_name", t.get("test_code", "")) for t in tests)
        try:
            result = self._agent(
                f"Patient is in {city} and needs: {names}. "
                f"Find nearby labs and choose one.",
                structured_output_model=LabChoice,
            )
            choice: LabChoice | None = result.structured_output
        except Exception as exc:  # noqa: BLE001
            log.warning("lab selection agent failed (%s) — falling back to ranking", exc)
            choice = None

        if choice is not None:
            for lab in candidates:
                lab["selected"] = lab.get("place_id") == choice.place_id
                lab["selection_reason"] = choice.reason if lab["selected"] else None
            if any(lab["selected"] for lab in candidates):
                return candidates
            log.warning("agent returned an unknown place_id — falling back to ranking")

        # Deterministic fallback. The cascade never stalls on a model.
        return places.select_lab(candidates, tests)

    def send_booking_request(self, *, lab: dict, test: dict, episode: dict) -> str:
        return ses.booking_request(lab=lab, test=test, episode=episode)

    def hold_slot(self, *, lab: dict, test: dict) -> str:
        return calendar_tool.hold_slot(lab=lab, test=test)

    def request_consult(self, *, episode: dict) -> dict:
        analysis = episode.get("analysis") or {}
        slot = calendar_tool.hold_slot(
            lab={"name": "Consultation", "address": ""},
            test={"display_name": "Follow-up consultation"},
            days_ahead=2,
        )
        try:
            ses.consult_request(episode=episode, analysis=analysis, slot=slot)
        except Exception as exc:  # noqa: BLE001
            log.warning("consult email failed (%s) — recording the request anyway", exc)
        from tools.store import now_iso

        return {
            "requested_at": now_iso(),
            "doctor": (episode.get("prescription") or {}).get("doctor") or "your doctor",
            "proposed_slot": slot,
            "status": "requested",
        }
