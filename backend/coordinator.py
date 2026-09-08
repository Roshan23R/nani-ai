"""The deterministic driver.

This file owns sequence. It is plain Python: a dispatch table from state to a
handler, each handler doing **one bounded step** and exactly one transition.
No LLM is consulted about what happens next — agents are called for content
(what the tests are, which lab, whether a change matters) and their answers
never choose the next state.

One step per call is also what keeps the API deployable behind API Gateway,
which hard-kills a request at 29 seconds. `advance()` returns after a single
transition; the UI's 3-second poll and the EventBridge tick drive the rest.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from agents.intake import run_intake
from agents.stubs import StubDiagnostics, StubLogistics
from state import idempotency
from state.machine import (
    State,
    confirmation_required,
    route_after_extraction,
)
from tools import store

log = logging.getLogger(__name__)


class Logistics(Protocol):
    def find_labs(self, *, city: str, tests: list[dict]) -> list[dict]: ...
    def send_booking_request(self, *, lab: dict, test: dict, episode: dict) -> str: ...
    def hold_slot(self, *, lab: dict, test: dict) -> str: ...
    def request_consult(self, *, episode: dict) -> dict: ...


class Diagnostics(Protocol):
    def read_report(self, *, file_bytes: bytes, filename: str) -> list[dict]: ...
    def assess(self, *, values: list[dict], history: dict) -> dict: ...


class Coordinator:
    def __init__(
        self,
        *,
        logistics: Logistics | None = None,
        diagnostics: Diagnostics | None = None,
        storage=None,
        stub: bool = False,
    ) -> None:
        """`stub=True` gives canned agents: no email, no Bedrock, no cost."""
        if stub:
            self.logistics: Logistics = logistics or StubLogistics()
            self.diagnostics: Diagnostics = diagnostics or StubDiagnostics()
            self.storage = storage or (lambda data, name: f"local://{name}")
            return

        from agents.diagnostics import DiagnosticsAgent
        from agents.logistics import LogisticsAgent
        from tools import s3

        self.logistics = logistics or LogisticsAgent()
        self.diagnostics = diagnostics or DiagnosticsAgent()
        self.storage = storage or (lambda data, name: s3.put_upload(data, name))

    # --- entry points ------------------------------------------------------

    def start_episode(self, patient_id: str, file_bytes: bytes, filename: str) -> dict:
        """Patient uploads a prescription. Returns immediately after intake."""
        episode = store.new_episode(patient_id, upload_name=filename)
        episode["_source"] = {"filename": filename, "url": self.storage(file_bytes, filename)}
        store.put_episode(episode)
        return self.advance(episode, file_bytes=file_bytes)

    def confirm(self, episode: dict, tests: list[dict]) -> dict:
        """Patient confirmed or corrected the extracted tests."""
        if episode["state"] != State.AWAITING_CONFIRMATION.value:
            raise ValueError(f"Episode is in {episode['state']}, not awaiting confirmation")

        kept = [t for t in tests if t.get("keep", True)]
        extracted = (episode.get("confirmation") or {}).get("extracted_tests") or []
        edits = _count_edits(extracted, tests)

        episode["prescription"]["tests"] = [
            {k: t[k] for k in ("test_code", "display_name", "urgency") if k in t}
            for t in kept
        ]
        episode["confirmation"] = {
            **(episode.get("confirmation") or {}),
            "confirmed_at": store.now_iso(),
            "confirmed_tests": episode["prescription"]["tests"],
            "edits_made": edits,
        }
        removed = len(extracted) - len(kept)
        detail = f"{len(kept)} of {len(extracted)} tests confirmed"
        if removed:
            detail += f", {removed} removed"
        store.add_timeline(episode, "patient", "confirmed_tests", detail)
        episode = self._shortlist_labs(episode)
        store.put_episode(episode)
        return episode

    def deliver_report(self, episode: dict, file_bytes: bytes, filename: str) -> dict:
        """A lab report arrived, by upload or by landing in the S3 inbox."""
        if episode["state"] != State.AWAITING_REPORT.value:
            raise ValueError(f"Episode is in {episode['state']}, not awaiting a report")
        episode["report"] = {
            "received_at": store.now_iso(),
            "source_file_url": self.storage(file_bytes, filename),
            "values": [],
        }
        episode["_report_bytes_name"] = filename
        store.apply_transition(
            episode,
            State.REPORT_RECEIVED,
            actor="patient",
            action="uploaded_report",
            detail=filename,
            summary_line="Report received, reading it now",
        )
        store.put_episode(episode)
        return self.advance(episode, file_bytes=file_bytes)

    def retry(self, episode: dict) -> dict:
        """Come back out of NEEDS_HUMAN, into the state we escalated from."""
        if episode["state"] != State.NEEDS_HUMAN.value:
            raise ValueError(f"Episode is in {episode['state']}, not NEEDS_HUMAN")
        target = episode.get("_retry_from") or State.PRESCRIPTION_RECEIVED.value
        episode["error"] = None
        store.apply_transition(
            episode,
            target,
            actor="patient",
            action="retried",
            detail=f"retrying from {target}",
            summary_line="Trying again",
        )
        store.put_episode(episode)
        return episode

    # --- the driver --------------------------------------------------------

    def advance(self, episode: dict, *, file_bytes: bytes | None = None) -> dict:
        """Perform one step of work, if the current state has one pending."""
        handler = self._HANDLERS.get(State(episode["state"]))
        if handler is None:
            return episode
        try:
            episode = handler(self, episode, file_bytes)
        except Exception as exc:  # noqa: BLE001 — any failure escalates, never crashes
            log.exception("step failed in %s", episode["state"])
            return self._escalate(
                episode,
                code="EXTRACTION_FAILED",
                message=f"Something went wrong while processing this episode: {exc}",
                action_hint="Try again, or upload the document once more.",
            )
        store.put_episode(episode)
        return episode

    def drive(self, episode: dict, *, max_steps: int = 20) -> dict:
        """Advance until the episode reaches a state with nothing pending.

        Those resting states — AWAITING_CONFIRMATION, AWAITING_REPORT,
        NEEDS_HUMAN, CLOSED — each wait on someone outside the machine, and the
        chains between them are short enough to run inside one request:

            upload -> AWAITING_CONFIRMATION   ~13s   (intake dominates)
            upload -> AWAITING_REPORT         ~19s   (high confidence path)
            confirm -> AWAITING_REPORT         ~6s
            report -> CLOSED                  ~10s

        All comfortably inside API Gateway's hard 29-second cut-off, but that
        headroom is why no single handler may grow a second LLM call.
        """
        for _ in range(max_steps):
            before = episode["state"]
            episode = self.advance(episode)
            if episode["state"] == before:
                break
        return episode

    # --- handlers, one per state ------------------------------------------

    def _read_prescription(self, episode: dict, file_bytes: bytes | None) -> dict:
        if file_bytes is None:
            return episode
        result = run_intake_bytes(file_bytes, episode["_source"]["filename"])

        if result.extraction is None:
            return self._escalate(
                episode,
                code="PRESCRIPTION_UNREADABLE",
                message="The prescription could not be read clearly.",
                action_hint="Try uploading a clearer photo in good light.",
                retry_to=State.PRESCRIPTION_RECEIVED,
            )

        ex = result.extraction
        episode["prescription"] = {
            "doctor": ex.get("doctor"),
            "date": ex.get("date"),
            "diagnosis": ex.get("diagnosis"),
            "medicines": ex.get("medicines") or [],
            "tests": ex.get("tests") or [],
            "source_file_url": episode["_source"]["url"],
        }
        # Stored for completeness, never displayed — both are known-unreliable.
        episode["_extraction"] = {
            "confidence": ex.get("confidence"),
            "exam_findings": ex.get("exam_findings") or [],
            "unreadable_fields": ex.get("unreadable_fields") or [],
        }

        n = len(result.tests)
        store.apply_transition(
            episode,
            State.TESTS_IDENTIFIED,
            actor="intake_agent",
            action="extracted_tests",
            detail=f"{n} test(s) found, confidence {result.confidence}",
            summary_line=f"{n} test{'s' if n != 1 else ''} identified on your prescription",
        )
        if result.needs_human:
            # Two different failures wearing one gate. Telling someone to
            # retake a photo of a perfectly legible prescription that simply
            # orders no tests is worse than useless.
            if result.confidence == "low":
                return self._escalate(
                    episode,
                    code="PRESCRIPTION_UNREADABLE",
                    message="The handwriting on this prescription could not be read reliably.",
                    action_hint="Try a clearer photo in good light, or enter the tests yourself.",
                )
            return self._escalate(
                episode,
                code="EXTRACTION_FAILED",
                message="No diagnostic tests were found on this prescription.",
                action_hint=(
                    "If your doctor did order tests, upload a clearer photo — "
                    "otherwise there is nothing to book."
                ),
                retry_to=State.PRESCRIPTION_RECEIVED,
            )
        return episode

    def _route_after_intake(self, episode: dict, _bytes) -> dict:
        # A tick can reach an episode whose prescription never landed — a crash
        # mid-intake, or a hand-edited row. Escalate rather than blow up the
        # whole tick loop for every other episode behind it.
        if not (episode.get("prescription") or {}).get("tests"):
            return self._escalate(
                episode,
                code="EXTRACTION_FAILED",
                message="This episode has no extracted tests to act on.",
                action_hint="Upload the prescription again.",
                retry_to=State.PRESCRIPTION_RECEIVED,
            )
        confidence = (episode.get("_extraction") or {}).get("confidence")
        target = route_after_extraction(needs_human=False, confidence=confidence)

        if target is State.AWAITING_CONFIRMATION:
            tests = episode["prescription"]["tests"]
            episode["confirmation"] = {
                "required": True,
                "confirmed_at": None,
                "extracted_tests": tests,
                "confirmed_tests": None,
                "edits_made": None,
            }
            store.apply_transition(
                episode,
                State.AWAITING_CONFIRMATION,
                actor="intake_agent",
                action="awaiting_confirmation",
                detail=f"{len(tests)} tests read from prescription — asked patient to confirm",
                summary_line="Confirm what we read",
            )
            return episode

        # High confidence: the agent acts without asking.
        episode["confirmation"] = {
            "required": False,
            "confirmed_at": None,
            "extracted_tests": episode["prescription"]["tests"],
            "confirmed_tests": episode["prescription"]["tests"],
            "edits_made": 0,
        }
        store.add_timeline(
            episode,
            "intake_agent",
            "skipped_confirmation",
            "extraction confidence high — proceeding without asking",
        )
        return self._shortlist_labs(episode)

    def _shortlist_labs(self, episode: dict) -> dict:
        tests = episode["prescription"]["tests"]
        patient = store.get_patient(episode["patient_id"]) or {}
        labs = self.logistics.find_labs(city=patient.get("city", "Kolkata"), tests=tests)
        episode["labs"] = labs

        if not labs:
            return self._escalate(
                episode,
                code="NO_LABS_FOUND",
                message="No diagnostic labs were found nearby.",
                action_hint="Try again, or widen the search area.",
            )
        store.apply_transition(
            episode,
            State.LABS_SHORTLISTED,
            actor="logistics_agent",
            action="found_labs",
            detail=f"{len(labs)} centres found",
            summary_line=f"{len(labs)} nearby labs found",
        )
        return episode

    def _request_bookings(self, episode: dict, _bytes) -> dict:
        lab = next((l for l in episode["labs"] if l.get("selected")), episode["labs"][0])
        sent = 0

        for test in episode["prescription"]["tests"]:
            key = idempotency.claim_key(episode["episode_id"], test["test_code"])
            if not idempotency.acquire(
                key, episode_id=episode["episode_id"], purpose="booking_email"
            ):
                log.info("booking already claimed, skipping: %s", key)
                continue

            self.logistics.send_booking_request(lab=lab, test=test, episode=episode)
            episode["bookings"].append(
                {
                    "test_code": test["test_code"],
                    "lab_name": lab["name"],
                    "requested_at": store.now_iso(),
                    "status": "requested",
                    "slot_hold": self.logistics.hold_slot(lab=lab, test=test),
                    "idempotency_key": key,
                }
            )
            sent += 1

        store.apply_transition(
            episode,
            State.BOOKING_REQUESTED,
            actor="logistics_agent",
            action="requested_booking",
            detail=f"{sent} booking request(s) sent to {lab['name']}",
            summary_line=f"Booking requested at {lab['name']}",
        )
        return episode

    def _await_report(self, episode: dict, _bytes) -> dict:
        store.apply_transition(
            episode,
            State.AWAITING_REPORT,
            actor="logistics_agent",
            action="awaiting_report",
            detail="waiting for the lab to send results",
            summary_line="Booked — waiting for your results",
        )
        return episode

    def _check_inbox(self, episode: dict, _bytes) -> dict:
        """Has a lab dropped a report for this episode yet?

        This is the second trigger and the reason the project is an agent
        rather than a form: nobody presses a button, the heartbeat notices.
        """
        from tools import s3

        found = s3.find_report(episode["episode_id"])
        if found is None:
            return episode  # still waiting; no transition, no timeline noise

        data, filename = found
        episode["report"] = {
            "received_at": store.now_iso(),
            "source_file_url": f"s3://{s3.S3_BUCKET}/{s3.inbox_key(episode['episode_id'], filename)}",
            "values": [],
        }
        episode["_report_bytes_name"] = filename
        store.apply_transition(
            episode,
            State.REPORT_RECEIVED,
            actor="scheduler",
            action="found_report",
            detail=f"{filename} arrived in the inbox",
            summary_line="Report received, reading it now",
        )
        return self._analyse_report(episode, data)

    def _analyse_report(self, episode: dict, file_bytes: bytes | None) -> dict:
        values = self.diagnostics.read_report(
            file_bytes=file_bytes or b"", filename=episode.get("_report_bytes_name", "report")
        )
        if not values:
            return self._escalate(
                episode,
                code="REPORT_UNREADABLE",
                message="The lab report could not be read.",
                action_hint="Upload a clearer copy of the report.",
            )

        pid = episode["patient_id"]
        for v in values:
            v["flag"] = _flag(v)
            history = store.get_history(pid, v["test_code"])
            today = store.now_iso()[:10]
            history = [h for h in history if h["date"] != today]
            history.append({"date": today, "value": v["value"]})
            v["history"] = history
            v["trend"] = _trend(history)
            store.put_result(pid, v["test_code"], today, v["value"], v.get("unit", ""))

        episode["report"]["values"] = values
        moving = [v for v in values if v["trend"] in ("rising", "falling")]
        store.apply_transition(
            episode,
            State.TRENDS_ANALYZED,
            actor="diagnostics_agent",
            action="compared_history",
            detail=f"{len(values)} value(s) read, {len(moving)} moving against history",
            summary_line=f"{len(values)} result(s) compared against your history",
        )
        return episode

    def _decide_significance(self, episode: dict, _bytes) -> dict:
        values = episode["report"]["values"]
        analysis = self.diagnostics.assess(
            values=values, history={v["test_code"]: v["history"] for v in values}
        )
        episode["analysis"] = analysis

        if analysis.get("consult_needed"):
            store.apply_transition(
                episode,
                State.ANOMALY_FOUND,
                actor="diagnostics_agent",
                action="flagged_anomaly",
                detail=analysis["findings"][0] if analysis.get("findings") else "",
                summary_line="Something changed — a follow-up is worth booking",
            )
        else:
            store.apply_transition(
                episode,
                State.NORMAL,
                actor="diagnostics_agent",
                action="no_action_needed",
                detail="nothing outside the reference ranges",
                summary_line="Your results look normal",
            )
        return episode

    def _request_consult(self, episode: dict, _bytes) -> dict:
        key = idempotency.claim_key(episode["episode_id"], "CONSULT")
        if idempotency.acquire(key, episode_id=episode["episode_id"], purpose="consult_email"):
            episode["consultation"] = self.logistics.request_consult(episode=episode)
            detail = f"follow-up requested with {episode['consultation']['doctor']}"
        else:
            # Already sent on an earlier tick. Do not send twice; just move on.
            detail = "consult already requested on an earlier run"
        store.apply_transition(
            episode,
            State.CONSULT_REQUESTED,
            actor="logistics_agent",
            action="requested_consult",
            detail=detail,
            summary_line="Follow-up consultation requested",
        )
        return episode

    def _close(self, episode: dict, _bytes) -> dict:
        store.apply_transition(
            episode,
            State.CLOSED,
            actor="scheduler",
            action="closed_episode",
            detail="episode complete",
            summary_line="Episode complete",
        )
        return episode

    # --- escalation --------------------------------------------------------

    def _escalate(
        self,
        episode: dict,
        *,
        code: str,
        message: str,
        action_hint: str,
        retry_to: State | str | None = None,
    ) -> dict:
        """Escalate to NEEDS_HUMAN, recording where a retry should resume.

        `retry_to` matters: resuming an extraction failure at TESTS_IDENTIFIED
        just re-runs the same failing check on the next tick and bounces
        straight back here. Those retries belong at the upload step, where the
        patient can supply a better photo.
        """
        episode["_retry_from"] = str(retry_to or episode["state"])
        store.set_error(episode, code, message, action_hint, retryable=True)
        store.apply_transition(
            episode,
            State.NEEDS_HUMAN,
            actor="scheduler",
            action="escalated",
            detail=message,
            summary_line="We need your help to continue",
        )
        store.put_episode(episode)
        return episode

    _HANDLERS = {
        State.PRESCRIPTION_RECEIVED: _read_prescription,
        State.TESTS_IDENTIFIED: _route_after_intake,
        State.LABS_SHORTLISTED: _request_bookings,
        State.BOOKING_REQUESTED: _await_report,
        State.AWAITING_REPORT: _check_inbox,
        State.REPORT_RECEIVED: _analyse_report,
        State.TRENDS_ANALYZED: _decide_significance,
        State.ANOMALY_FOUND: _request_consult,
        State.CONSULT_REQUESTED: _close,
        State.NORMAL: _close,
        # AWAITING_CONFIRMATION, NEEDS_HUMAN and CLOSED have no pending work:
        # each waits on a person. AWAITING_REPORT does have work — checking the
        # inbox — which is why it is in the table and they are not.
    }


# --- helpers ---------------------------------------------------------------

def run_intake_bytes(file_bytes: bytes, filename: str):
    """Run intake on in-memory bytes by staging them to a temp file."""
    import os
    import tempfile

    suffix = os.path.splitext(filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
        fh.write(file_bytes)
        path = fh.name
    try:
        return run_intake(path)
    finally:
        os.unlink(path)


def _flag(value: dict) -> str:
    v, lo, hi = value.get("value"), value.get("ref_low"), value.get("ref_high")
    if v is None or lo is None or hi is None:
        return "normal"
    if v < lo:
        return "low"
    if v > hi:
        return "high"
    return "normal"


def _trend(history: list[dict]) -> str:
    if len(history) < 2:
        return "first_reading"
    latest, previous = history[-1]["value"], history[-2]["value"]
    if previous in (None, 0):
        return "stable"
    delta = (latest - previous) / abs(previous)
    if delta > 0.05:
        return "rising"
    if delta < -0.05:
        return "falling"
    return "stable"


def _count_edits(extracted: list[dict], submitted: list[dict]) -> int:
    by_code = {t.get("test_code"): t for t in extracted}
    edits = 0
    for t in submitted:
        original = by_code.get(t.get("test_code"))
        if original is None or not t.get("keep", True):
            edits += 1
            continue
        if t.get("display_name") != original.get("display_name"):
            edits += 1
        elif t.get("urgency") != original.get("urgency"):
            edits += 1
    return edits
