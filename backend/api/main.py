"""The endpoints the UI calls.

Shapes come from the frozen contract (`client/api-contract.md`, plus
`docs/api-contract-v2.md` §4 for the confirmation step). Nothing here decides
anything: handlers validate input, call the coordinator, and return the episode.

Every handler completes one bounded chain of steps and returns. That is what
keeps it deployable behind API Gateway, which kills a request at 29 seconds.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from coordinator import Coordinator
from state.machine import POLLING_STOPS, State
from tools import store

log = logging.getLogger(__name__)

# Lambda leaves non-root loggers at WARNING, which silences the tick summary
# — the one line that says what the heartbeat actually did.
logging.getLogger().setLevel(logging.INFO)

app = FastAPI(title="Nani AI", docs_url="/api/docs", redoc_url=None)

# The frontend is a static export on another origin, so it needs CORS. The
# submission is a public demo; there is nothing user-specific to protect.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

coordinator = Coordinator()


# --- helpers ---------------------------------------------------------------

def public(episode: dict) -> dict:
    """Strip internal bookkeeping. Underscore keys never cross the wire."""
    return {k: v for k, v in episode.items() if not k.startswith("_")}


def fail(status: int, code: str, message: str, retryable: bool = False):
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "retryable": retryable}},
    )


def load(episode_id: str) -> dict:
    episode = store.get_episode(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    """HTTP errors use the same error object shape as episode errors."""
    codes = {404: "NOT_FOUND", 400: "BAD_REQUEST", 409: "CONFLICT"}
    return fail(exc.status_code, codes.get(exc.status_code, "ERROR"), str(exc.detail))


# --- request models --------------------------------------------------------

class ConfirmTest(BaseModel):
    test_code: str
    display_name: str
    urgency: str = "routine"
    keep: bool = True


class ConfirmBody(BaseModel):
    tests: list[ConfirmTest]


# --- endpoints -------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "nani-ai"}


@app.get("/api/patients")
def list_patients():
    return store.list_patients()


@app.get("/api/episodes")
def list_episodes(patient_id: str):
    return store.list_episodes(patient_id)


@app.post("/api/episodes", status_code=201)
async def create_episode(patient_id: str = Form(...), file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        return fail(400, "EXTRACTION_FAILED", "The uploaded file was empty.", True)
    episode = coordinator.start_episode(patient_id, data, file.filename or "prescription.jpg")
    episode = coordinator.drive(episode)
    return public(episode)


@app.get("/api/episodes/{episode_id}")
def get_episode(episode_id: str):
    return public(load(episode_id))


@app.post("/api/episodes/{episode_id}/confirm")
def confirm(episode_id: str, body: ConfirmBody):
    episode = load(episode_id)
    if episode["state"] != State.AWAITING_CONFIRMATION.value:
        raise HTTPException(409, f"Episode is in {episode['state']}, not awaiting confirmation")
    if not any(t.keep for t in body.tests):
        return fail(400, "EXTRACTION_FAILED", "At least one test must be kept.", True)

    episode = coordinator.confirm(episode, [t.model_dump() for t in body.tests])
    return public(coordinator.drive(episode))


@app.post("/api/episodes/{episode_id}/report")
async def upload_report(episode_id: str, file: UploadFile = File(...)):
    episode = load(episode_id)
    if episode["state"] != State.AWAITING_REPORT.value:
        raise HTTPException(409, f"Episode is in {episode['state']}, not awaiting a report")
    data = await file.read()
    episode = coordinator.deliver_report(episode, data, file.filename or "report.pdf")
    return public(coordinator.drive(episode))


@app.post("/api/episodes/{episode_id}/retry")
def retry(episode_id: str):
    episode = load(episode_id)
    if episode["state"] != State.NEEDS_HUMAN.value:
        raise HTTPException(409, f"Episode is in {episode['state']}, nothing to retry")
    return public(coordinator.retry(episode))


@app.post("/api/tick")
def tick(patient_id: str | None = None):
    """The heartbeat. EventBridge Scheduler calls this; nothing else should.

    Walks every episode that still has pending work. Episodes resting in
    AWAITING_CONFIRMATION, NEEDS_HUMAN or CLOSED are skipped — they wait on a
    person, not on us.
    """
    moved, checked = [], 0
    for profile in store.list_patients() if patient_id is None else [{"patient_id": patient_id}]:
        for summary in store.list_episodes(profile["patient_id"]):
            checked += 1
            if State(summary["state"]) in POLLING_STOPS:
                continue
            episode = store.get_episode(summary["episode_id"])
            if episode is None:
                continue
            before = episode["state"]
            episode = coordinator.advance(episode)
            if episode["state"] != before:
                moved.append(
                    {"episode_id": episode["episode_id"], "from": before, "to": episode["state"]}
                )
    return {"checked": checked, "advanced": moved}


# --- Lambda entry point ----------------------------------------------------

try:  # only present in the Lambda bundle
    from mangum import Mangum

    _asgi = Mangum(app, lifespan="off")
except ImportError:  # pragma: no cover
    _asgi = None


def handler(event, context):
    """One Lambda, two callers.

    API Gateway sends an HTTP event, which Mangum turns into an ASGI request.
    EventBridge Scheduler sends `{"nani_tick": true}` and skips ASGI entirely —
    the heartbeat has no HTTP semantics worth faking, and going through the
    gateway would put a 29-second ceiling on a job that walks every episode.
    """
    if isinstance(event, dict) and event.get("nani_tick"):
        result = tick()
        log.info("tick: checked %s, advanced %s", result["checked"], len(result["advanced"]))
        return result
    return _asgi(event, context)
