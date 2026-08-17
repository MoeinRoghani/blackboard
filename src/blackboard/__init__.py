"""A skeletal blackboard system.

The library supplies the board, the shared structure through which
independent agents contribute to one result, and the write path of the
control component: a write made through it passes admission before the
board sequences it. The public surface is the set of names in ``__all__``;
every other name is internal.
"""

from blackboard._board import (
    BlackboardError,
    Board,
    BoardChange,
    Conflict,
    Contribution,
    DuplicateRegionError,
    Level,
    RegionKindError,
    Register,
    RegisterState,
    UndeclaredRegionError,
    UnsetRegisterError,
    Written,
)
from blackboard._clock import Clock, ManualClock, ScheduledCall, SystemClock
from blackboard._control import (
    Accept,
    Accepted,
    AdmissionRule,
    AuditEvent,
    BoardReader,
    ProposedContribution,
    ProposedRegisterWrite,
    ProposedWrite,
    Reject,
    Rejected,
    RejectionCause,
    WriteAccepted,
    WriteRejected,
)

__all__ = [
    "Accept",
    "Accepted",
    "AdmissionRule",
    "AuditEvent",
    "BlackboardError",
    "Board",
    "BoardChange",
    "BoardReader",
    "Clock",
    "Conflict",
    "Contribution",
    "DuplicateRegionError",
    "Level",
    "ManualClock",
    "ProposedContribution",
    "ProposedRegisterWrite",
    "ProposedWrite",
    "RegionKindError",
    "Register",
    "RegisterState",
    "Reject",
    "Rejected",
    "RejectionCause",
    "ScheduledCall",
    "SystemClock",
    "UndeclaredRegionError",
    "UnsetRegisterError",
    "WriteAccepted",
    "WriteRejected",
    "Written",
]
