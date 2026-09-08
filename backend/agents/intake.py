"""Intake agent — prescription in, structured extraction plus a gate decision out.

Reads a prescription image or PDF and returns what the doctor actually wrote.
Runs on the SMART model: Haiku fabricates tests that were never on the page
(CLAUDE.md, "Extraction findings"), and an invented test sends a patient to pay
for a procedure their doctor never ordered.

The gate is the safety property. `confidence == "low"`, no tests, or output we
cannot parse all mean NEEDS_HUMAN. This agent reports *content* — whether the
extraction is trustworthy. `coordinator.py` owns the state transition.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from strands import Agent
from strands.types.content import ContentBlock

from agents.prompts import SYSTEM_PROMPT, USER_PROMPT
from agents.strands_setup import (
    JSONParseError,
    MODEL_SMART,
    parse_json_response,
    response_text,
    smart_model,
)

# Bedrock's ImageFormat literal is png|jpeg|gif|webp — "jpg" is NOT valid and
# is rejected at the API boundary, so it must be normalised to "jpeg".
IMAGE_FORMATS = {"jpeg", "jpg", "png", "gif", "webp"}

PROCEED = "PROCEED"
NEEDS_HUMAN = "NEEDS_HUMAN"


@dataclass
class IntakeResult:
    """What intake learned, and whether it is safe to act on."""

    gate: str                              # PROCEED | NEEDS_HUMAN
    gate_reason: str
    extraction: dict[str, Any] | None
    raw_text: str
    model_id: str
    latency_s: float
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def tests(self) -> list[dict[str, Any]]:
        return (self.extraction or {}).get("tests", []) or []

    @property
    def confidence(self) -> str | None:
        return (self.extraction or {}).get("confidence")

    @property
    def needs_human(self) -> bool:
        return self.gate == NEEDS_HUMAN


def build_content_block(path: str) -> ContentBlock:
    """Wrap a local file as a Bedrock image or document content block."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    with open(path, "rb") as f:
        raw = f.read()

    if ext == "pdf":
        # Document names must be alphanumeric plus spaces/hyphens/parens.
        safe_name = (
            re.sub(r"[^A-Za-z0-9 \-()\[\]]", "", os.path.basename(path)) or "prescription"
        )
        return {"document": {"format": "pdf", "name": safe_name, "source": {"bytes": raw}}}

    if ext in IMAGE_FORMATS:
        fmt = "jpeg" if ext == "jpg" else ext
        return {"image": {"format": fmt, "source": {"bytes": raw}}}

    raise ValueError(
        f"Unsupported file type '{ext or path}'. Use jpg, png, gif, webp or pdf. "
        "(HEIC is not accepted by Bedrock — convert it first.)"
    )


def evaluate_gate(extraction: dict[str, Any]) -> tuple[str, str]:
    """Apply the intake gate. Never proceed on a weak extraction."""
    confidence = extraction.get("confidence")
    tests = extraction.get("tests") or []

    if confidence == "low":
        return NEEDS_HUMAN, "extraction confidence is low"
    if not tests:
        return NEEDS_HUMAN, "no investigations found on the prescription"
    return PROCEED, f"{len(tests)} test(s) extracted at confidence '{confidence}'"


def build_agent(model=None) -> Agent:
    """The intake agent. temperature=0 for every extraction call."""
    return Agent(
        model=model or smart_model(temperature=0.0, max_tokens=2000),
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )


def run_intake(path: str, *, model=None) -> IntakeResult:
    """Extract a prescription and decide whether it is safe to proceed."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    content = build_content_block(path)
    agent = build_agent(model)
    model_id = getattr(agent.model, "config", {}).get("model_id", MODEL_SMART)

    started = time.time()
    result = agent([content, {"text": USER_PROMPT}])
    latency = time.time() - started

    text = response_text(result)
    usage = dict(getattr(result.metrics, "accumulated_usage", None) or {})

    try:
        extraction = parse_json_response(text)
    except JSONParseError as exc:
        # Unparseable output is ambiguity, and ambiguity escalates.
        return IntakeResult(
            gate=NEEDS_HUMAN,
            gate_reason=f"model output was not valid JSON ({exc})",
            extraction=None,
            raw_text=exc.raw,
            model_id=model_id,
            latency_s=latency,
            usage=usage,
        )

    gate, reason = evaluate_gate(extraction)
    return IntakeResult(
        gate=gate,
        gate_reason=reason,
        extraction=extraction,
        raw_text=text,
        model_id=model_id,
        latency_s=latency,
        usage=usage,
    )
