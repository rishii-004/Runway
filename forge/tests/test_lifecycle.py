import pytest

from forge.runtime.lifecycle import (
    CANCELLED,
    COMPLETED,
    FAILED,
    QUEUED,
    RUNNING,
    TERMINAL_STATES,
    TRANSITIONS,
    WAITING_FOR_APPROVAL,
    can_transition,
    transition,
)


def test_queued_to_running():
    assert can_transition(QUEUED, RUNNING)


def test_queued_to_cancelled():
    assert can_transition(QUEUED, CANCELLED)


def test_queued_to_completed_invalid():
    assert not can_transition(QUEUED, COMPLETED)


def test_running_to_completed():
    assert can_transition(RUNNING, COMPLETED)


def test_running_to_failed():
    assert can_transition(RUNNING, FAILED)


def test_running_to_waiting_approval():
    assert can_transition(RUNNING, WAITING_FOR_APPROVAL)


def test_running_to_running():
    assert can_transition(RUNNING, RUNNING)


def test_waiting_approval_to_running():
    assert can_transition(WAITING_FOR_APPROVAL, RUNNING)


def test_waiting_approval_to_cancelled():
    assert can_transition(WAITING_FOR_APPROVAL, CANCELLED)


def test_terminal_states_no_transitions():
    for state in TERMINAL_STATES:
        assert not TRANSITIONS.get(state)


def test_transition_raises_on_invalid():
    with pytest.raises(ValueError, match="Invalid transition"):
        transition(COMPLETED, RUNNING)


def test_transition_succeeds_on_valid():
    result = transition(QUEUED, RUNNING)
    assert result == RUNNING
