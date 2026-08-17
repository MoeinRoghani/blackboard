"""A skeletal blackboard system.

The library supplies the board, the shared structure through which
independent agents contribute to one result, and the control component's
write path and notification dispatch: a write made through it passes
admission before the board sequences it, and an admitted register write
notifies every other registered agent. The public surface is the set of
names in ``__all__``; every other name is internal.
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
    Agent,
    AuditEvent,
    BoardReader,
    DeadlineExtended,
    DuplicateAgentError,
    Notification,
    NotificationAcknowledged,
    NotificationDispatched,
    NotificationId,
    PresumedFailed,
    ProposedContribution,
    ProposedRegisterWrite,
    ProposedWrite,
    Reject,
    Rejected,
    RejectionCause,
    UnknownNotificationError,
    WakeCapReached,
    WriteAccepted,
    WriteRejected,
)

__all__ = [
    "Accept",
    "Accepted",
    "AdmissionRule",
    "Agent",
    "AuditEvent",
    "BlackboardError",
    "Board",
    "BoardChange",
    "BoardReader",
    "Clock",
    "Conflict",
    "Contribution",
    "DeadlineExtended",
    "DuplicateAgentError",
    "DuplicateRegionError",
    "Level",
    "ManualClock",
    "Notification",
    "NotificationAcknowledged",
    "NotificationDispatched",
    "NotificationId",
    "PresumedFailed",
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
    "UnknownNotificationError",
    "UnsetRegisterError",
    "WakeCapReached",
    "WriteAccepted",
    "WriteRejected",
    "Written",
]
