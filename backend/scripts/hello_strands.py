"""Smoke test: does Strands actually talk to Bedrock on this account?

Run this before debugging anything else. If it fails, the problem is
credentials, region or Bedrock model access — not your agent code.

    backend/venv/bin/python backend/scripts/hello_strands.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strands import Agent  # noqa: E402

from agents.strands_setup import (  # noqa: E402
    AWS_REGION,
    MODEL_SMART,
    response_text,
)
from agents.strands_setup import smart_model  # noqa: E402


def main() -> int:
    print(f"region : {AWS_REGION}")
    print(f"model  : {MODEL_SMART}")
    print("-" * 72)

    agent = Agent(
        model=smart_model(max_tokens=100),
        system_prompt="You are a terse smoke test. Answer in one short line.",
        callback_handler=None,  # suppress token streaming to stdout
    )

    started = time.time()
    try:
        result = agent("Reply with exactly: Strands is talking to Bedrock.")
    except Exception as exc:  # noqa: BLE001 - surface whatever Bedrock says
        print(f"FAILED: {type(exc).__name__}: {exc}")
        print(
            "\nIf this is AccessDeniedException, request access to the model in the\n"
            "Bedrock console. If it is a credentials error, check `~/.aws/credentials`."
        )
        return 1

    elapsed = time.time() - started
    print(response_text(result))
    print("-" * 72)

    usage = getattr(result.metrics, "accumulated_usage", None) or {}
    print(f"stop reason   : {result.stop_reason}")
    print(f"tokens in/out : {usage.get('inputTokens')}/{usage.get('outputTokens')}")
    print(f"latency       : {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
