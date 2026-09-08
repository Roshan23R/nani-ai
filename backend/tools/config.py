"""Runtime configuration.

Reads `backend/.env` locally (gitignored) and plain environment variables in
Lambda, where the same keys arrive from Secrets Manager. Nothing here has a
real secret as a default — an absent credential makes the matching tool fall
back to its stub and say so, rather than failing at the worst moment.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# --- Google ---------------------------------------------------------------
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

# --- SES ------------------------------------------------------------------
# Sandbox: sends only to verified addresses, 1/second, 200/day. All of these
# are verified on the account already.
SES_SENDER = os.environ.get("SES_SENDER", "shekharshashank1211@gmail.com")
SES_LAB_RECIPIENT = os.environ.get("SES_LAB_RECIPIENT", "shekharshashank1211+lab@gmail.com")
SES_DOCTOR_RECIPIENT = os.environ.get("SES_DOCTOR_RECIPIENT", "shekharshashank1211+doctor@gmail.com")
SES_SEND_INTERVAL = float(os.environ.get("SES_SEND_INTERVAL", "1.1"))

# --- S3 -------------------------------------------------------------------
S3_BUCKET = os.environ.get("S3_BUCKET", "nani-ai-storage-018695127621-us-east-1-an")
S3_INBOX_PREFIX = os.environ.get("S3_INBOX_PREFIX", "inbox/")
S3_UPLOAD_PREFIX = os.environ.get("S3_UPLOAD_PREFIX", "uploads/")

# --- switches -------------------------------------------------------------
#: Set NANI_DRY_RUN=1 to build emails without handing them to SES.
DRY_RUN = os.environ.get("NANI_DRY_RUN", "").lower() in ("1", "true", "yes")


def has_places() -> bool:
    return bool(GOOGLE_PLACES_API_KEY)


def has_calendar() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN)


def describe() -> dict[str, str]:
    """What is live and what is stubbed. Printed by the scripts on startup."""
    return {
        "places": "live" if has_places() else "STUB (no GOOGLE_PLACES_API_KEY)",
        "calendar": "live" if has_calendar() else "STUB (no Google OAuth refresh token)",
        "ses": "dry-run" if DRY_RUN else "live (sandbox)",
        "s3": S3_BUCKET,
    }
