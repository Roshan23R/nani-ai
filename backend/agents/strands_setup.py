"""Shared Strands + Bedrock plumbing.

Model IDs come from the environment so the same code runs against whatever is
actually enabled on the account. Defaults match the Config block in CLAUDE.md.

Routing rule (see "Extraction findings" in CLAUDE.md — do not re-litigate):
  SMART (Sonnet 4.5)  extraction, the significance decision
  FAST  (Haiku 4.5)   summary writing, lab selection. NEVER extraction —
                      it invents tests that were not on the page.
"""

from __future__ import annotations

import json
import os
import re

from strands.models import BedrockModel

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

MODEL_SMART = os.environ.get(
    "BEDROCK_MODEL_SMART", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)
MODEL_FAST = os.environ.get(
    "BEDROCK_MODEL_FAST", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)

DEFAULT_MAX_TOKENS = 2000


def bedrock_model(
    model_id: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    **overrides,
) -> BedrockModel:
    """A BedrockModel with the project's defaults applied."""
    return BedrockModel(
        region_name=AWS_REGION,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        **overrides,
    )


def smart_model(**overrides) -> BedrockModel:
    """Sonnet 4.5. Extraction and the significance call only."""
    return bedrock_model(MODEL_SMART, **overrides)


def fast_model(**overrides) -> BedrockModel:
    """Haiku 4.5. Summaries and lab selection. Not extraction."""
    return bedrock_model(MODEL_FAST, **overrides)


class JSONParseError(ValueError):
    """Model output could not be parsed as JSON. Carries the raw text."""

    def __init__(self, message: str, raw: str) -> None:
        super().__init__(message)
        self.raw = raw


# Matches a fenced block anywhere in the output, not just at the very ends —
# models occasionally emit a sentence of preamble before the fence despite
# being told not to.
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def strip_fences(text: str) -> str:
    """Return the most likely JSON payload inside a model response."""
    cleaned = text.strip()

    fenced = _FENCE_RE.search(cleaned)
    if fenced:
        return fenced.group(1).strip()

    if cleaned.startswith(("{", "[")):
        return cleaned

    # Last resort: the outermost brace pair, dropping any prose around it.
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        return cleaned[start : end + 1].strip()

    return cleaned


def parse_json_response(text: str) -> dict:
    """Parse model output into a dict, stripping markdown fences first.

    Raises JSONParseError with the raw text attached, so callers can gate to
    NEEDS_HUMAN and still log what the model actually said.
    """
    cleaned = strip_fences(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise JSONParseError(f"Model did not return valid JSON: {exc}", raw=text) from exc

    if not isinstance(parsed, dict):
        raise JSONParseError(
            f"Expected a JSON object, got {type(parsed).__name__}", raw=text
        )
    return parsed


def response_text(result) -> str:
    """Concatenate the text blocks of a Strands AgentResult."""
    content = (result.message or {}).get("content", [])
    return "".join(block.get("text", "") for block in content).strip()
