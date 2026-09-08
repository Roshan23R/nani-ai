"""Diagnostics agent — read the report, compare, decide whether it matters.

Two calls with deliberately different models:

  * **Reading** the report is extraction, so it runs on the smart model for the
    same reason intake does. Reference ranges come from the report itself —
    Indian lab reports print them, and a hardcoded range table would be wrong
    for half the labs in the country and dangerously wrong for some.
  * **Significance** is the one judgement call in the whole system that earns
    the stronger model. It is also the only place the project spends a smart
    call per episode rather than per document.

The output summarises and flags. It never diagnoses, and it never tells anyone
what to do about a result.
"""

from __future__ import annotations

import json
import logging

from strands import Agent

from agents.intake import build_content_block
from agents.strands_setup import (
    JSONParseError,
    parse_json_response,
    response_text,
    smart_model,
)

log = logging.getLogger(__name__)

READ_PROMPT = """You read Indian diagnostic lab reports and return structured values.

Return ONLY a JSON object. No preamble, no markdown fences.

{
  "values": [
    {
      "test_code": string,        // short uppercase, e.g. HB, TSH, FBS, VITD
      "display_name": string,     // as printed on the report
      "value": number,
      "unit": string,
      "ref_low": number or null,
      "ref_high": number or null
    }
  ],
  "unreadable_fields": [string]
}

## Reference ranges

Indian lab reports print their own reference range next to each value, usually
as "12.0 - 15.0" or "Normal: 12-15". **Read the range off the page.** Never
supply a range from your own knowledge — labs differ, and the printed one is
the only one that applies to this result.

If a range is genuinely not printed, set ref_low and ref_high to null and say
so in unreadable_fields. Null is correct; a guessed range is not.

## Values

Only numeric results. Skip anything qualitative ("Negative", "Nil seen") — it
does not trend. If a value is illegible, leave it out and note it in
unreadable_fields rather than guessing a plausible number.

Do not invent tests. If the report shows three results, return three."""

ASSESS_PROMPT = """You decide whether a change in a patient's lab results is worth a doctor's time.

Return ONLY a JSON object. No preamble, no markdown fences.

{
  "severity": "normal" | "attention" | "urgent",
  "consult_needed": true | false,
  "findings": [string],
  "patient_summary": string
}

## What you are deciding

Not "is this abnormal" — the flags already say that. You are deciding whether
something **changed meaningfully** against this patient's own history, or sits
far enough outside the printed range to be worth acting on now.

- A value drifting inside the normal range is not a finding.
- A value that has moved consistently in one direction across three readings is
  a finding even if it is still in range.
- A value newly outside its printed range is a finding.
- A single reading a hair outside the range, with no history, is "attention" at
  most, never "urgent".

## severity

- "normal": nothing needs a doctor
- "attention": worth discussing at the next opportunity
- "urgent": needs attention now — use this sparingly and only for values far
  outside range

## Tone

`findings` is for the doctor: factual, one line each, name the value and the
movement.

`patient_summary` is for a worried person reading it on a phone. Plain words,
two sentences at most, no jargon. Say what was seen and that a doctor should
look. **Never name a disease, never suggest a cause, never recommend treatment
or medication.** You summarise and flag; you do not diagnose."""


class DiagnosticsAgent:
    """The interface the coordinator drives. Same shape as StubDiagnostics."""

    name = "diagnostics"

    def __init__(self) -> None:
        self._reader = Agent(
            model=smart_model(temperature=0.0, max_tokens=2000),
            system_prompt=READ_PROMPT,
            callback_handler=None,
        )
        self._assessor = Agent(
            model=smart_model(temperature=0.0, max_tokens=1000),
            system_prompt=ASSESS_PROMPT,
            callback_handler=None,
        )

    def read_report(self, *, file_bytes: bytes, filename: str) -> list[dict]:
        import os
        import tempfile

        suffix = os.path.splitext(filename)[1] or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
            fh.write(file_bytes)
            path = fh.name
        try:
            content = build_content_block(path)
        except ValueError as exc:
            log.warning("unsupported report format: %s", exc)
            return []
        finally:
            pass

        try:
            result = self._reader([content, {"text": "Extract the values from this report."}])
            parsed = parse_json_response(response_text(result))
        except (JSONParseError, Exception) as exc:  # noqa: BLE001
            log.warning("report read failed: %s", exc)
            return []
        finally:
            os.unlink(path)

        values = parsed.get("values") or []
        return [v for v in values if isinstance(v.get("value"), (int, float))]

    def assess(self, *, values: list[dict], history: dict) -> dict:
        payload = {
            "values": [
                {
                    k: v.get(k)
                    for k in ("test_code", "display_name", "value", "unit",
                              "ref_low", "ref_high", "flag", "trend")
                }
                for v in values
            ],
            "history": history,
        }
        try:
            result = self._assessor(
                "Assess these results against the patient's history:\n"
                + json.dumps(payload, ensure_ascii=False)
            )
            parsed = parse_json_response(response_text(result))
        except Exception as exc:  # noqa: BLE001
            log.warning("assessment failed (%s) — falling back to flags alone", exc)
            parsed = _fallback_assessment(values)

        parsed.setdefault("severity", "normal")
        parsed.setdefault("consult_needed", parsed["severity"] != "normal")
        parsed.setdefault("findings", [])
        parsed.setdefault("patient_summary", "")
        # Never model-generated: the disclaimer is ours, verbatim, every time.
        parsed["disclaimer"] = "This is not medical advice. A doctor should review these results."
        return parsed


def _fallback_assessment(values: list[dict]) -> dict:
    """If the model is unavailable, fall back to the printed ranges alone."""
    out_of_range = [v for v in values if v.get("flag") in ("low", "high")]
    if not out_of_range:
        return {
            "severity": "normal",
            "consult_needed": False,
            "findings": ["All values sit within the reference ranges printed on the report."],
            "patient_summary": "Everything on this report looks to be within the normal range.",
        }
    names = ", ".join(v.get("display_name", v.get("test_code", "")) for v in out_of_range)
    return {
        "severity": "attention",
        "consult_needed": True,
        "findings": [f"{names} outside the reference range printed on the report."],
        "patient_summary": (
            f"Your {names.lower()} is outside the normal range printed on your report. "
            "This is worth showing to your doctor."
        ),
    }
