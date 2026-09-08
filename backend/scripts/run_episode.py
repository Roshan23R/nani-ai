"""Walk one episode from upload to CLOSED, printing the timeline.

The end-to-end rehearsal. Uses stub logistics and diagnostics by default, so it
sends no email and costs nothing beyond the intake call.

    backend/venv/bin/python backend/scripts/run_episode.py demo-data/IMG_2070.jpg
    backend/venv/bin/python backend/scripts/run_episode.py demo-data/IMG_2071.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coordinator import Coordinator  # noqa: E402
from tools.config import describe  # noqa: E402
from state.machine import State  # noqa: E402
from tools import store  # noqa: E402

BAR = "─" * 78


def show(episode: dict, seen: int) -> int:
    for entry in episode["timeline"][seen:]:
        print(f"  {entry['at'][11:19]}  {entry['actor']:<18} {entry['action']:<24} {entry['detail']}")
    return len(episode["timeline"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", help="Prescription image or PDF")
    ap.add_argument("--patient", default="demo-patient-01")
    ap.add_argument("--report", help="Lab report to deliver once booked")
    ap.add_argument("--json", action="store_true", help="Dump the final episode")
    ap.add_argument("--stub", action="store_true",
                    help="Canned agents: no Bedrock, no email, no cost")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"error: {path} not found", file=sys.stderr)
        return 2

    coord = Coordinator(stub=args.stub)
    print(f"\n{BAR}")
    print("  " + "   ".join(f"{k}={v}" for k, v in describe().items())
          if not args.stub else "  all agents stubbed")
    print(f"{BAR}\nupload   {path.name}   patient {args.patient}\n{BAR}")

    episode = coord.start_episode(args.patient, path.read_bytes(), path.name)
    episode = coord.drive(episode)
    seen = show(episode, 0)
    print(f"{BAR}\nstate    {episode['state']}   —   {episode['summary_line']}")

    if episode["state"] == State.AWAITING_CONFIRMATION.value:
        tests = episode["confirmation"]["extracted_tests"]
        print(f"\n  patient confirms all {len(tests)} tests\n{BAR}")
        episode = coord.confirm(episode, [{**t, "keep": True} for t in tests])
        episode = coord.drive(episode)
        seen = show(episode, seen)
        print(f"{BAR}\nstate    {episode['state']}   —   {episode['summary_line']}")

    if episode["state"] == State.AWAITING_REPORT.value:
        report = Path(args.report) if args.report else None
        data = report.read_bytes() if report and report.exists() else b"stub-report"
        name = report.name if report else "report.pdf"
        print(f"\n  lab delivers {name}\n{BAR}")
        episode = coord.deliver_report(episode, data, name)
        episode = coord.drive(episode)
        seen = show(episode, seen)
        print(f"{BAR}\nstate    {episode['state']}   —   {episode['summary_line']}")

    print(f"{BAR}")
    print(f"episode  {episode['episode_id']}")
    print(f"final    {episode['state']}")
    print(f"steps    {len(episode['timeline'])} timeline entries")
    if episode.get("error"):
        print(f"error    {episode['error']['code']}: {episode['error']['message']}")
    if episode.get("bookings"):
        print(f"bookings {len(episode['bookings'])} — keys "
              f"{[b['idempotency_key'] for b in episode['bookings']]}")
    print(f"{BAR}\n")

    if args.json:
        print(json.dumps({k: v for k, v in episode.items() if not k.startswith("_")},
                         indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
