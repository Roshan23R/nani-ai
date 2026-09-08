"""The deterministic state machine.

This module is the project's core safety property. Every transition an episode
makes is checked here, in plain Python. **No LLM decides a state transition** —
agents decide *content* (which tests, which lab, whether a change matters) and
the coordinator decides *sequence* using this table.

An illegal transition raises. It is not logged and skipped, not clamped to the
nearest legal state — it raises, because a state machine you can bypass is not a
safety property, it is a diagram.

Routing after extraction (decided Sep 8, supersedes the blanket-confirmation
rule): confidence gates how much autonomy the agent takes.

    low / no tests  →  NEEDS_HUMAN            cannot read it, ask a person
    medium          →  AWAITING_CONFIRMATION  read it, show the patient first
    high            →  LABS_SHORTLISTED       read it well, book autonomously

The middle row is the interesting one. A blanket "always confirm" is not
judgement, it is an agent declining to act on its own read regardless of how
good that read was. Escalating in proportion to uncertainty is.
"""

from __future__ import annotations

from enum import Enum


class State(str, Enum):
    """Every state an episode can occupy.

    Values match the frozen API contract exactly — the frontend switches on
    these strings, so they are not ours to rename.
    """

    PRESCRIPTION_RECEIVED = "PRESCRIPTION_RECEIVED"
    TESTS_IDENTIFIED = "TESTS_IDENTIFIED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    COVERAGE_CHECKED = "COVERAGE_CHECKED"
    LABS_SHORTLISTED = "LABS_SHORTLISTED"
    BOOKING_REQUESTED = "BOOKING_REQUESTED"
    AWAITING_REPORT = "AWAITING_REPORT"
    REPORT_RECEIVED = "REPORT_RECEIVED"
    TRENDS_ANALYZED = "TRENDS_ANALYZED"
    ANOMALY_FOUND = "ANOMALY_FOUND"
    NORMAL = "NORMAL"
    CONSULT_REQUESTED = "CONSULT_REQUESTED"
    CLOSED = "CLOSED"
    NEEDS_HUMAN = "NEEDS_HUMAN"

    def __str__(self) -> str:  # so f-strings print the bare name
        return self.value


#: The episode is over. No outbound transitions exist.
FINAL: frozenset[State] = frozenset({State.CLOSED})

#: The UI stops its 3-second poll here. Not the same as FINAL: an episode can
#: sit in AWAITING_CONFIRMATION or NEEDS_HUMAN for days and still resume.
#: NORMAL is included because the frontend already treats it as terminal.
POLLING_STOPS: frozenset[State] = frozenset(
    {State.NORMAL, State.CLOSED, State.NEEDS_HUMAN, State.AWAITING_CONFIRMATION}
)

#: States an episode can be escalated out of, and retried back into.
LIVE: frozenset[State] = frozenset(set(State) - {State.CLOSED, State.NEEDS_HUMAN})

# The happy-path graph, before NEEDS_HUMAN edges are woven in.
#
# COVERAGE_CHECKED is defined and wired so the machine matches the documented
# contract, but the coverage feature is CUT for this build — nothing routes to
# it today. Enabling it later is a coordinator change, not a machine change.
_FLOW: dict[State, frozenset[State]] = {
    State.PRESCRIPTION_RECEIVED: frozenset({State.TESTS_IDENTIFIED}),
    # Three-way split on extraction confidence. See route_after_extraction.
    State.TESTS_IDENTIFIED: frozenset(
        {State.AWAITING_CONFIRMATION, State.COVERAGE_CHECKED, State.LABS_SHORTLISTED}
    ),
    # PRESCRIPTION_RECEIVED is the "I need to re-upload" path from the
    # confirmation screen (contract v2 §4.4).
    State.AWAITING_CONFIRMATION: frozenset(
        {State.COVERAGE_CHECKED, State.LABS_SHORTLISTED, State.PRESCRIPTION_RECEIVED}
    ),
    State.COVERAGE_CHECKED: frozenset({State.LABS_SHORTLISTED}),
    State.LABS_SHORTLISTED: frozenset({State.BOOKING_REQUESTED}),
    State.BOOKING_REQUESTED: frozenset({State.AWAITING_REPORT}),
    State.AWAITING_REPORT: frozenset({State.REPORT_RECEIVED}),
    State.REPORT_RECEIVED: frozenset({State.TRENDS_ANALYZED}),
    State.TRENDS_ANALYZED: frozenset({State.ANOMALY_FOUND, State.NORMAL}),
    State.ANOMALY_FOUND: frozenset({State.CONSULT_REQUESTED}),
    State.CONSULT_REQUESTED: frozenset({State.CLOSED}),
    State.NORMAL: frozenset({State.CLOSED}),
    State.CLOSED: frozenset(),
    State.NEEDS_HUMAN: frozenset(),
}

# NEEDS_HUMAN is reachable from every live state, and retryable back into any
# of them. The coordinator supplies the state the episode was escalated from;
# this table only says the move is permitted.
ALLOWED: dict[State, frozenset[State]] = {
    state: (targets | {State.NEEDS_HUMAN} if state in LIVE else targets)
    for state, targets in _FLOW.items()
}
ALLOWED[State.NEEDS_HUMAN] = LIVE


class IllegalTransition(Exception):
    """An episode was asked to make a move the machine does not permit."""

    def __init__(self, frm: State, to: State) -> None:
        legal = ", ".join(sorted(s.value for s in ALLOWED.get(frm, frozenset())))
        super().__init__(
            f"{frm} -> {to} is not a legal transition. "
            f"From {frm} the episode may go to: {legal or '(nowhere — terminal)'}"
        )
        self.frm = frm
        self.to = to


def coerce(value: State | str) -> State:
    """Turn a contract string into a State, with a useful error if it isn't one."""
    if isinstance(value, State):
        return value
    try:
        return State(value)
    except ValueError:
        known = ", ".join(s.value for s in State)
        raise ValueError(f"Unknown state {value!r}. Known states: {known}") from None


def successors(frm: State | str) -> frozenset[State]:
    """Every state legally reachable in one step."""
    return ALLOWED[coerce(frm)]


def can(frm: State | str, to: State | str) -> bool:
    """Is this transition permitted?"""
    return coerce(to) in ALLOWED[coerce(frm)]


def assert_legal(frm: State | str, to: State | str) -> State:
    """Check a transition and return the destination. Raises if illegal.

    Call this on the way into every state change. It is the single choke point
    the whole safety argument rests on.
    """
    frm_s, to_s = coerce(frm), coerce(to)
    if to_s not in ALLOWED[frm_s]:
        raise IllegalTransition(frm_s, to_s)
    return to_s


def is_final(state: State | str) -> bool:
    """The episode is over."""
    return coerce(state) in FINAL


def polling_stops(state: State | str) -> bool:
    """The UI should stop its 3-second poll. Not the same as finished."""
    return coerce(state) in POLLING_STOPS


def route_after_extraction(
    *,
    needs_human: bool,
    confidence: str | None,
    has_policy: bool = False,
) -> State:
    """Where an episode goes once intake has read the prescription.

    Deterministic. `needs_human` is intake's own trust gate (low confidence or
    no tests found) — this function does not re-derive it, so the rule lives in
    exactly one place.

    `has_policy` routes through the coverage check. Always False today; the
    feature is cut.
    """
    if needs_human:
        return State.NEEDS_HUMAN
    if confidence == "high":
        return State.COVERAGE_CHECKED if has_policy else State.LABS_SHORTLISTED
    return State.AWAITING_CONFIRMATION


def confirmation_required(confidence: str | None) -> bool:
    """Value for `episode.confirmation.required` in the API response.

    False when the agent read the prescription well enough to act alone.
    """
    return confidence != "high"
