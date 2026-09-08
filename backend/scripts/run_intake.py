"""Run the intake agent against a prescription and print the gate decision.

    backend/venv/bin/python backend/scripts/run_intake.py demo-data/IMG_2070.jpg
    backend/venv/bin/python backend/scripts/run_intake.py demo-data/rx.pdf --json

Unlike scripts/test_extraction.py (which compares raw models), this exercises
the real agent path: agents/intake.py, the shared model config, and the gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.intake import NEEDS_HUMAN, run_intake  # noqa: E402
from agents.strands_setup import AWS_REGION  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", help="Prescription image (jpg/png/gif/webp) or PDF")
    ap.add_argument("--json", action="store_true",
                    help="Print only the extraction JSON, for piping")
    args = ap.parse_args()

    try:
        result = run_intake(args.file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.extraction, indent=2, ensure_ascii=False))
        return 0 if not result.needs_human else 1

    print(f"\nfile   : {args.file}")
    print(f"model  : {result.model_id}")
    print(f"region : {AWS_REGION}")
    print("-" * 72)

    if result.extraction is None:
        print("!! Model did not return valid JSON. Raw output:\n")
        print(result.raw_text)
    else:
        print(json.dumps(result.extraction, indent=2, ensure_ascii=False))
        print("-" * 72)
        e = result.extraction
        print(f"tests found   : {len(result.tests)}")
        for t in result.tests:
            print(f"                - {t.get('test_code')}: {t.get('display_name')} "
                  f"[{t.get('urgency')}]")
        print(f"medicines     : {len(e.get('medicines') or [])}")
        print(f"exam findings : {len(e.get('exam_findings') or [])}")
        print(f"confidence    : {result.confidence}")
        if e.get("unreadable_fields"):
            print(f"unreadable    : {', '.join(e['unreadable_fields'])}")

    print("-" * 72)
    marker = ">>> GATE" if result.gate == NEEDS_HUMAN else ">>> GATE"
    print(f"{marker}: {result.gate} — {result.gate_reason}")
    if result.gate == NEEDS_HUMAN:
        print("    coordinator would route this episode to NEEDS_HUMAN (retryable)")
    else:
        print("    coordinator would advance to TESTS_IDENTIFIED, then "
              "AWAITING_CONFIRMATION")

    u = result.usage
    print("-" * 72)
    print(f"tokens in/out : {u.get('inputTokens')}/{u.get('outputTokens')}")
    print(f"latency       : {result.latency_s:.1f}s\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
