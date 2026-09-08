"""The state machine is the project's core safety property. Test it like one."""

import re
from pathlib import Path

import pytest

from state.machine import (
    ALLOWED,
    FINAL,
    LIVE,
    POLLING_STOPS,
    IllegalTransition,
    State,
    assert_legal,
    can,
    confirmation_required,
    is_final,
    polling_stops,
    route_after_extraction,
    successors,
)

HAPPY_PATH = [
    State.PRESCRIPTION_RECEIVED,
    State.TESTS_IDENTIFIED,
    State.AWAITING_CONFIRMATION,
    State.LABS_SHORTLISTED,
    State.BOOKING_REQUESTED,
    State.AWAITING_REPORT,
    State.REPORT_RECEIVED,
    State.TRENDS_ANALYZED,
    State.ANOMALY_FOUND,
    State.CONSULT_REQUESTED,
    State.CLOSED,
]


# --- table integrity -------------------------------------------------------

def test_every_state_has_an_entry():
    assert set(ALLOWED) == set(State)


def test_every_target_is_a_real_state():
    for frm, targets in ALLOWED.items():
        for to in targets:
            assert isinstance(to, State), f"{frm} -> {to!r} is not a State"


def test_closed_is_final_and_has_no_exit():
    assert is_final(State.CLOSED)
    assert successors(State.CLOSED) == frozenset()


def test_every_state_is_reachable_from_the_start():
    seen, frontier = {State.PRESCRIPTION_RECEIVED}, [State.PRESCRIPTION_RECEIVED]
    while frontier:
        for nxt in successors(frontier.pop()):
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    assert seen == set(State), f"unreachable: {set(State) - seen}"


# --- escalation ------------------------------------------------------------

def test_needs_human_is_reachable_from_every_live_state():
    for state in LIVE:
        assert can(state, State.NEEDS_HUMAN), f"cannot escalate from {state}"


def test_needs_human_is_retryable_into_every_live_state():
    assert successors(State.NEEDS_HUMAN) == LIVE


def test_needs_human_cannot_retry_into_a_finished_episode():
    assert not can(State.NEEDS_HUMAN, State.CLOSED)


# --- the actual guarantee --------------------------------------------------

def test_the_happy_path_walks_legally():
    for frm, to in zip(HAPPY_PATH, HAPPY_PATH[1:]):
        assert_legal(frm, to)


def test_skipping_confirmation_to_book_is_illegal():
    """The whole point: you cannot jump straight to booking."""
    with pytest.raises(IllegalTransition):
        assert_legal(State.TESTS_IDENTIFIED, State.BOOKING_REQUESTED)


def test_cannot_run_the_cascade_backwards():
    with pytest.raises(IllegalTransition):
        assert_legal(State.AWAITING_REPORT, State.LABS_SHORTLISTED)


def test_illegal_transition_says_what_was_legal():
    with pytest.raises(IllegalTransition, match=r"may go to:.*TESTS_IDENTIFIED"):
        assert_legal(State.PRESCRIPTION_RECEIVED, State.CLOSED)


def test_reupload_from_confirmation_is_allowed():
    """Contract v2 §4.4 — the 'I need to re-upload' secondary action."""
    assert_legal(State.AWAITING_CONFIRMATION, State.PRESCRIPTION_RECEIVED)


# --- confidence routing ----------------------------------------------------

@pytest.mark.parametrize(
    "needs_human,confidence,has_policy,expected",
    [
        (True, "low", False, State.NEEDS_HUMAN),
        (True, None, False, State.NEEDS_HUMAN),
        (False, "medium", False, State.AWAITING_CONFIRMATION),
        (False, None, False, State.AWAITING_CONFIRMATION),
        (False, "high", False, State.LABS_SHORTLISTED),
        (False, "high", True, State.COVERAGE_CHECKED),
    ],
)
def test_routing_after_extraction(needs_human, confidence, has_policy, expected):
    assert route_after_extraction(
        needs_human=needs_human, confidence=confidence, has_policy=has_policy
    ) is expected


def test_every_routing_destination_is_a_legal_move():
    """Routing and the transition table must not disagree."""
    for needs_human in (True, False):
        for confidence in ("low", "medium", "high", None):
            for has_policy in (True, False):
                target = route_after_extraction(
                    needs_human=needs_human,
                    confidence=confidence,
                    has_policy=has_policy,
                )
                assert can(State.TESTS_IDENTIFIED, target), (
                    f"router returns {target} but the table forbids "
                    f"TESTS_IDENTIFIED -> {target}"
                )


def test_high_confidence_skips_confirmation():
    assert confirmation_required("high") is False
    for c in ("medium", "low", None):
        assert confirmation_required(c) is True


# --- UI contract -----------------------------------------------------------

def test_polling_stops_where_the_patient_must_act():
    assert polling_stops(State.AWAITING_CONFIRMATION)
    assert polling_stops(State.NEEDS_HUMAN)
    assert not polling_stops(State.BOOKING_REQUESTED)


def test_awaiting_confirmation_stops_polling_but_is_not_final():
    assert State.AWAITING_CONFIRMATION in POLLING_STOPS
    assert State.AWAITING_CONFIRMATION not in FINAL
    assert successors(State.AWAITING_CONFIRMATION)


def test_frontend_states_all_exist_in_the_machine():
    """Catches drift against the frozen contract's EpisodeState union."""
    types_ts = Path(__file__).resolve().parents[2] / "client/src/care/types.ts"
    block = re.search(
        r"export type EpisodeState =(.*?)\n\n", types_ts.read_text(), re.DOTALL
    )
    assert block, "could not find the EpisodeState union in types.ts"
    frontend = set(re.findall(r"'([A-Z_]+)'", block.group(1)))
    assert frontend, "parsed no states out of types.ts"
    missing = frontend - {s.value for s in State}
    assert not missing, f"frontend knows states the backend does not: {missing}"
