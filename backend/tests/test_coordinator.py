"""The cascade, driven with stub agents — no Bedrock, no email, no cost.

These cover sequence and safety. Extraction quality is not testable here and is
covered by running the real prescriptions through scripts/run_intake.py.
"""

import pytest

from agents.stubs import StubDiagnostics, StubLogistics
from coordinator import Coordinator, _count_edits, _flag, _trend
from state.machine import State


@pytest.fixture
def coord():
    return Coordinator(stub=True)


@pytest.fixture
def episode():
    """An episode parked at TESTS_IDENTIFIED with four tests, in memory only."""
    from tools import store

    ep = store.new_episode("test-patient", upload_name="rx.jpg")
    ep["prescription"] = {
        "doctor": "Dr Test", "date": None, "diagnosis": None, "medicines": [],
        "tests": [
            {"test_code": c, "display_name": c, "urgency": "routine"}
            for c in ("CBC", "FBS", "VITD", "FT4TSH")
        ],
        "source_file_url": "local://rx.jpg",
    }
    ep["state"] = State.TESTS_IDENTIFIED.value
    return ep


# --- confidence routing through the real coordinator -----------------------

def test_medium_confidence_stops_for_confirmation(coord, episode, monkeypatch):
    monkeypatch.setattr("tools.store.put_episode", lambda e: e)
    episode["_extraction"] = {"confidence": "medium"}
    out = coord._route_after_intake(episode, None)
    assert out["state"] == State.AWAITING_CONFIRMATION.value
    assert out["confirmation"]["required"] is True
    assert len(out["confirmation"]["extracted_tests"]) == 4


def test_high_confidence_books_without_asking(coord, episode, monkeypatch):
    monkeypatch.setattr("tools.store.put_episode", lambda e: e)
    monkeypatch.setattr("tools.store.get_patient", lambda p: {"city": "Kolkata"})
    episode["_extraction"] = {"confidence": "high"}
    out = coord._route_after_intake(episode, None)
    assert out["state"] == State.LABS_SHORTLISTED.value
    assert out["confirmation"]["required"] is False
    assert any(e["action"] == "skipped_confirmation" for e in out["timeline"])


def test_an_episode_with_no_tests_escalates(coord, episode, monkeypatch):
    monkeypatch.setattr("tools.store.put_episode", lambda e: e)
    episode["prescription"]["tests"] = []
    out = coord._route_after_intake(episode, None)
    assert out["state"] == State.NEEDS_HUMAN.value
    assert out["error"]["retryable"] is True


# --- idempotency, the property the scheduler depends on --------------------

def test_a_second_fire_sends_no_second_email(coord, episode, monkeypatch):
    monkeypatch.setattr("tools.store.put_episode", lambda e: e)
    monkeypatch.setattr("tools.store.get_patient", lambda p: {"city": "Kolkata"})

    sent: list[str] = []
    claimed: set[str] = set()

    class Counting(StubLogistics):
        def send_booking_request(self, *, lab, test, episode):
            sent.append(test["test_code"])
            return "x"

    # In-memory stand-in for the DynamoDB conditional write.
    def fake_acquire(key, *, episode_id, purpose=""):
        from state.idempotency import ClaimResult

        if key in claimed:
            return ClaimResult(key=key, acquired=False)
        claimed.add(key)
        return ClaimResult(key=key, acquired=True)

    monkeypatch.setattr("state.idempotency.acquire", fake_acquire)
    coord.logistics = Counting()

    ep = coord._shortlist_labs(episode)
    coord._request_bookings(ep, None)
    assert len(sent) == 4

    ep["state"] = State.LABS_SHORTLISTED.value  # the scheduler fires again
    coord._request_bookings(ep, None)
    assert len(sent) == 4, f"duplicate emails leaked: {sent}"


# --- pure helpers ----------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ({"value": 9.6, "ref_low": 12.0, "ref_high": 15.0}, "low"),
        ({"value": 16.0, "ref_low": 12.0, "ref_high": 15.0}, "high"),
        ({"value": 13.0, "ref_low": 12.0, "ref_high": 15.0}, "normal"),
        ({"value": 13.0, "ref_low": None, "ref_high": None}, "normal"),
    ],
)
def test_flag_uses_the_printed_range(value, expected):
    assert _flag(value) == expected


@pytest.mark.parametrize(
    "history,expected",
    [
        ([{"value": 12.4}], "first_reading"),
        ([{"value": 12.4}, {"value": 9.6}], "falling"),
        ([{"value": 9.6}, {"value": 12.4}], "rising"),
        ([{"value": 12.0}, {"value": 12.1}], "stable"),
    ],
)
def test_trend(history, expected):
    assert _trend(history) == expected


def test_edits_are_counted_for_the_confirmation_record():
    extracted = [
        {"test_code": "CBC", "display_name": "CBC", "urgency": "routine"},
        {"test_code": "TSH", "display_name": "TSH", "urgency": "routine"},
    ]
    submitted = [
        {"test_code": "CBC", "display_name": "Complete blood count", "urgency": "routine", "keep": True},
        {"test_code": "TSH", "display_name": "TSH", "urgency": "routine", "keep": False},
    ]
    assert _count_edits(extracted, submitted) == 2


def test_stub_diagnostics_never_omits_the_disclaimer():
    values = [{"display_name": "Haemoglobin", "flag": "low"}]
    assert "not medical advice" in StubDiagnostics().assess(values=values, history={})["disclaimer"]
