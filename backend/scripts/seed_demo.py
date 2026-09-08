"""Seed demo patients and prior results.

**Every name here is invented.** The real prescriptions in `demo-data/` carry
real patient names; those never reach a screen, a seeded record, or the video.
`demo-data/` is gitignored and stays that way.

The prior HB readings exist so the trend comparison has something to compare
against — a trend with one data point is not a trend, and the falling line is
the most legible thing in the whole demo.

    backend/venv/bin/python backend/scripts/seed_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import store  # noqa: E402

PATIENTS = [
    {"patient_id": "demo-patient-01", "name": "Meera Banerjee", "city": "Kolkata", "dob": "1984-03-12"},
    {"patient_id": "demo-patient-02", "name": "Arun Prasad", "city": "Kolkata", "dob": "1971-11-02"},
]

# Falling haemoglobin across three visits — the anomaly the demo turns on.
HISTORY = [
    ("demo-patient-01", "HB", "2026-02-11", 12.4, "g/dL"),
    ("demo-patient-01", "HB", "2026-05-19", 11.1, "g/dL"),
    ("demo-patient-01", "FBS", "2026-05-19", 92.0, "mg/dL"),
    ("demo-patient-02", "HB", "2026-06-02", 14.2, "g/dL"),
]


def purge_episodes() -> int:
    """Delete every episode row. Development scratch, not demo data."""
    from tools.dynamo import table
    from boto3.dynamodb.conditions import Attr

    t = table()
    removed = 0
    scan = t.scan(FilterExpression=Attr("PK").begins_with("EPISODE#"))
    for item in scan.get("Items", []):
        t.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
        removed += 1
    scan = t.scan(FilterExpression=Attr("SK").begins_with("EPISODE#"))
    for item in scan.get("Items", []):
        t.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
        removed += 1
    return removed


def main() -> int:
    if "--purge" in sys.argv:
        print(f"purged   {purge_episodes()} episode rows\n")

    for profile in PATIENTS:
        store.put_patient(profile)
        print(f"patient  {profile['patient_id']:<18} {profile['name']}")

    for patient_id, code, date, value, unit in HISTORY:
        store.put_result(patient_id, code, date, value, unit)
        print(f"result   {patient_id:<18} {code:<6} {date}  {value} {unit}")

    print()
    for profile in PATIENTS:
        hb = store.get_history(profile["patient_id"], "HB")
        print(f"{profile['patient_id']} HB history: {[h['value'] for h in hb]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
