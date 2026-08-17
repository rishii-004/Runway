from __future__ import annotations

import structlog

logger = structlog.get_logger()

# Valid run statuses from PRD §7.1
QUEUED = "QUEUED"
RUNNING = "RUNNING"
WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"
TIMEOUT = "TIMEOUT"
BUDGET_EXCEEDED = "BUDGET_EXCEEDED"

# Terminal states
TERMINAL_STATES = {COMPLETED, FAILED, CANCELLED, TIMEOUT, BUDGET_EXCEEDED}

# Legal transitions: from_state -> set of valid to_states
TRANSITIONS: dict[str, set[str]] = {
    QUEUED: {RUNNING, CANCELLED},
    RUNNING: {RUNNING, WAITING_FOR_APPROVAL, COMPLETED, FAILED, CANCELLED, TIMEOUT, BUDGET_EXCEEDED},
    WAITING_FOR_APPROVAL: {RUNNING, CANCELLED, FAILED},
}


def can_transition(current: str, target: str) -> bool:
    if current not in TRANSITIONS:
        return False
    return target in TRANSITIONS[current]


def transition(current: str, target: str) -> str:
    if not can_transition(current, target):
        raise ValueError(f"Invalid transition: {current} -> {target}")
    logger.info("status_transition", from_status=current, to_status=target)
    return target
