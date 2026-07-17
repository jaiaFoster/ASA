"""
ASA2 POS Status Transition Maps.

This module documents and validates allowed status transitions for POS record types.
It does NOT implement a workflow engine or make automatic state changes.
Transitions are used only for documentation and mechanical validation.
"""

# Allowed work-item status transitions
WORK_ITEM_TRANSITIONS = {
    "proposed": ["ready", "cancelled"],
    "ready": ["assigned", "cancelled"],
    "assigned": ["in_progress", "blocked", "cancelled"],
    "in_progress": ["blocked", "review", "cancelled"],
    "blocked": ["assigned", "in_progress", "cancelled"],
    "review": ["in_progress", "accepted", "rejected", "cancelled"],
    "accepted": [],   # terminal
    "rejected": [],   # terminal
    "cancelled": [],  # terminal
}

# Statuses that may NOT transition directly to accepted
# (i.e., must go through review first)
WORK_ITEM_MUST_NOT_DIRECTLY_ACCEPT = {
    "proposed", "ready", "assigned", "in_progress", "blocked",
}

# Allowed assignment status transitions
ASSIGNMENT_TRANSITIONS = {
    "draft": ["issued", "cancelled"],
    "issued": ["acknowledged", "cancelled"],
    "acknowledged": ["in_progress", "cancelled"],
    "in_progress": ["submitted", "blocked", "cancelled"],
    "blocked": ["in_progress", "cancelled"],
    "submitted": ["closed", "in_progress"],
    "closed": [],    # terminal
    "cancelled": [], # terminal
}

# Allowed decision status transitions
DECISION_TRANSITIONS = {
    "proposed": ["pending", "cancelled"],
    "pending": ["decided", "cancelled"],
    "decided": ["superseded"],
    "superseded": [], # terminal
    "cancelled": [],  # terminal
}


def is_valid_work_item_transition(from_status: str, to_status: str) -> bool:
    allowed = WORK_ITEM_TRANSITIONS.get(from_status, [])
    return to_status in allowed


def is_valid_assignment_transition(from_status: str, to_status: str) -> bool:
    allowed = ASSIGNMENT_TRANSITIONS.get(from_status, [])
    return to_status in allowed


def is_valid_decision_transition(from_status: str, to_status: str) -> bool:
    allowed = DECISION_TRANSITIONS.get(from_status, [])
    return to_status in allowed
