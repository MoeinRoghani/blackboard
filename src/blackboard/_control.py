"""The control component: the write path and notification dispatch.

A write made through the control component passes the application's
admission rule before the board sequences it. The rule sees the proposed
write with a read handle on the board and returns accept or a reasoned
rejection. An admitted level write is sequenced and audited. An admitted
register write may still fail with a conflict, which returns to the writer
unaudited. A rejected write returns its reason to the writer, never reaches
the board, and is audited without a sequence number.

An admitted register write also notifies every registered agent except its
writer, through each agent's batch window. Acknowledgment, extension,
presumed failure, and wake caps are tracked here.

The rule runs without the control component's lock, so two writes judged
at the same moment are both judged against the board as it was before
either landed. A register write closes that window with its expected
version; a level write does not, so a rule refusing duplicates bounds
concurrent duplicates rather than preventing them.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import partial
from typing import NewType, Protocol, TypeAlias

from blackboard._board import (
    BlackboardError,
    Board,
    BoardChange,
    Conflict,
    Contribution,
    Level,
    RegionKindError,
    Register,
    RegisterState,
    Written,
)
from blackboard._clock import Clock, ScheduledCall


class BoardReader(Protocol):
    """The three read operations, the handle the admission rule receives."""

    def read_level(self, level: str, from_sequence: int = 0) -> list[Contribution]:
        """Returns a level's contributions from the sequence bound, inclusive."""
        ...

    def read_register(self, register: str) -> RegisterState:
        """Returns a register's current value and version."""
        ...

    def read_board(self, from_sequence: int = 0) -> list[BoardChange]:
        """Returns every write to every region, in sequence order, from the bound."""
        ...


@dataclass(frozen=True)
class ProposedContribution:
    """A level write as the admission rule sees it, before sequencing."""

    agent: str
    level: str
    content: object


@dataclass(frozen=True)
class ProposedRegisterWrite:
    """A register write as the admission rule sees it, before sequencing."""

    writer: str
    register: str
    value: object
    expected_version: int


ProposedWrite: TypeAlias = ProposedContribution | ProposedRegisterWrite


@dataclass(frozen=True)
class Accept:
    """The admission rule's verdict admitting a proposed write."""


@dataclass(frozen=True)
class Reject:
    """The admission rule's verdict refusing a proposed write, with its reason."""

    reason: str


AdmissionRule: TypeAlias = Callable[[ProposedWrite, "BoardReader"], Accept | Reject]


class RejectionCause(Enum):
    """Why the control component refused a write.

    ``ADMISSION``: the admission rule rejected it. ``UNDECLARED_REGION``: the
    named region was never declared. ``BUDGET_EXHAUSTED``: a run-wide budget
    is exhausted. ``RUN_CLOSED``: the run has closed. ``BUDGET_EXHAUSTED``
    and ``RUN_CLOSED`` cannot occur until budgets and run outcomes exist;
    the set is closed now because a member added later breaks an exhaustive
    match.
    """

    ADMISSION = "admission"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UNDECLARED_REGION = "undeclared_region"
    RUN_CLOSED = "run_closed"


@dataclass(frozen=True)
class Accepted:
    """A write the control component admitted, with the sequence it received."""

    sequence: int


@dataclass(frozen=True)
class Rejected:
    """A write the control component refused, with the cause and its reason."""

    cause: RejectionCause
    reason: str


@dataclass(frozen=True)
class WriteAccepted:
    """The audit record of a write that reached the board."""

    at: datetime
    writer: str
    region: str
    sequence: int


@dataclass(frozen=True)
class WriteRejected:
    """The audit record of a refused write; it never reached the board."""

    at: datetime
    writer: str
    region: str
    cause: RejectionCause
    reason: str


NotificationId = NewType("NotificationId", int)


@dataclass(frozen=True)
class Notification:
    """One wake: the range it covers, the changed registers, and its deadline.

    It carries no values. The agent reads the registers itself, and reads
    whatever else on the board it wants.
    """

    notification_id: NotificationId
    agent: str
    from_sequence: int
    to_sequence: int
    registers: frozenset[str]
    deadline: datetime


@dataclass(frozen=True)
class Agent:
    """An agent declaration: identity, deadline, wake cap, and delivery.

    The control component invokes ``notify`` to deliver a notification, on
    the thread that closed the batch window, holding no lock. The callback
    may run the whole agent cycle inline or hand the notification to the
    application's own execution.
    """

    name: str
    acknowledgment_deadline: timedelta
    wake_cap: int
    notify: Callable[[Notification], None]

    def __post_init__(self) -> None:
        if self.acknowledgment_deadline <= timedelta(0):
            raise ValueError("an acknowledgment deadline is a positive duration")
        if self.wake_cap < 1:
            raise ValueError("a wake cap is at least one notification")


class DuplicateAgentError(BlackboardError):
    """A registration named an agent that is already registered."""


class UnknownNotificationError(BlackboardError):
    """The named notification was never issued to the acknowledging agent."""


@dataclass(frozen=True)
class NotificationDispatched:
    """The audit record of one notification leaving the control component."""

    at: datetime
    notification: Notification


@dataclass(frozen=True)
class NotificationAcknowledged:
    """The audit record of an agent reporting that it stopped."""

    at: datetime
    agent: str
    notification_id: NotificationId


@dataclass(frozen=True)
class DeadlineExtended:
    """The audit record of a new deadline granted before the old one passed."""

    at: datetime
    agent: str
    notification_id: NotificationId
    new_deadline: datetime


@dataclass(frozen=True)
class PresumedFailed:
    """The audit record of a deadline passing with no acknowledgment."""

    at: datetime
    agent: str
    notification_id: NotificationId


@dataclass(frozen=True)
class WakeCapReached:
    """The audit record of an agent receiving the last notification its cap allows."""

    at: datetime
    agent: str


AuditEvent: TypeAlias = (
    WriteAccepted
    | WriteRejected
    | NotificationDispatched
    | NotificationAcknowledged
    | DeadlineExtended
    | PresumedFailed
    | WakeCapReached
)

_Delivery: TypeAlias = tuple[Callable[[Notification], None], Notification]


@dataclass
class _AgentState:
    declaration: Agent
    cursor: int
    wake_count: int = 0
    capped: bool = False
    pending: dict[str, datetime] = field(default_factory=dict)
    window_call: ScheduledCall | None = None
    window_due: datetime | None = None
    window_generation: int = 0


@dataclass
class _Outstanding:
    deadline_call: ScheduledCall
    to_sequence: int
    generation: int = 0


def _accept_every_write(
    proposed: ProposedWrite, reader: BoardReader
) -> Accept | Reject:
    return Accept()


class _RegionKind(Enum):
    LEVEL = "level"
    REGISTER = "register"


class Control:
    """The control component's write path, over a board it owns."""

    def __init__(
        self,
        *,
        regions: Iterable[Level | Register] = (),
        admission_rule: AdmissionRule | None = None,
        clock: Clock,
    ) -> None:
        self._board = Board()
        self._clock = clock
        self._admission_rule = (
            admission_rule if admission_rule is not None else _accept_every_write
        )
        self._lock = threading.Lock()
        self._kinds: dict[str, _RegionKind] = {}
        self._batch_windows: dict[str, timedelta] = {}
        self._audit: list[AuditEvent] = []
        self._in_flight = 0
        self._last_sequence = 0
        self._agents: dict[str, _AgentState] = {}
        self._issued: set[tuple[str, NotificationId]] = set()
        self._outstanding: dict[tuple[str, NotificationId], _Outstanding] = {}
        self._presumed_failed: set[str] = set()
        self._next_notification_id = 1
        self._delivery_queue: deque[_Delivery] = deque()
        self._delivering = threading.local()
        for region in regions:
            self.declare(region)

    @property
    def reader(self) -> BoardReader:
        """The board's read side. Reads bypass the control component entirely."""
        return self._board

    def declare(self, region: Level | Register) -> None:
        """Creates a region on the board and records its kind."""
        with self._lock:
            self._board.declare(region)
            if isinstance(region, Level):
                self._kinds[region.name] = _RegionKind.LEVEL
            else:
                self._kinds[region.name] = _RegionKind.REGISTER
                self._batch_windows[region.name] = region.batch_window

    def register_agent(self, agent: Agent) -> None:
        """Registers an agent. Its cursor starts at the current sequence number."""
        with self._lock:
            if agent.name in self._agents:
                raise DuplicateAgentError(
                    f"an agent named {agent.name!r} is already registered"
                )
            self._agents[agent.name] = _AgentState(
                declaration=agent, cursor=self._last_sequence
            )

    def write(self, agent: str, level: str, content: object) -> Accepted | Rejected:
        """Runs one level write through admission and, if admitted, the board."""
        refusal = self._refuse_region(agent, level, _RegionKind.LEVEL)
        if refusal is not None:
            return refusal
        with self._lock:
            self._in_flight += 1
        try:
            proposed = ProposedContribution(agent=agent, level=level, content=content)
            verdict = self._admission_rule(proposed, self._board)
            if isinstance(verdict, Reject):
                return self._reject(
                    agent, level, RejectionCause.ADMISSION, verdict.reason
                )
            with self._lock:
                sequence = self._board.append(level, content)
                self._last_sequence = sequence
                self._audit.append(
                    WriteAccepted(
                        at=self._clock.now(),
                        writer=agent,
                        region=level,
                        sequence=sequence,
                    )
                )
            return Accepted(sequence=sequence)
        finally:
            with self._lock:
                self._in_flight -= 1

    def set_register(
        self, writer: str, register: str, value: object, expected_version: int
    ) -> Written | Conflict | Rejected:
        """Runs one register write through admission and, if admitted, the board."""
        refusal = self._refuse_region(writer, register, _RegionKind.REGISTER)
        if refusal is not None:
            return refusal
        with self._lock:
            self._in_flight += 1
        try:
            proposed = ProposedRegisterWrite(
                writer=writer,
                register=register,
                value=value,
                expected_version=expected_version,
            )
            verdict = self._admission_rule(proposed, self._board)
            if isinstance(verdict, Reject):
                return self._reject(
                    writer, register, RejectionCause.ADMISSION, verdict.reason
                )
            deliveries: list[_Delivery] = []
            with self._lock:
                result = self._board.set(register, value, expected_version)
                if isinstance(result, Written):
                    self._last_sequence = result.sequence
                    self._audit.append(
                        WriteAccepted(
                            at=self._clock.now(),
                            writer=writer,
                            region=register,
                            sequence=result.sequence,
                        )
                    )
                    deliveries = self._note_register_change(register, writer)
        finally:
            with self._lock:
                self._in_flight -= 1
        self._deliver(deliveries)
        return result

    def read_audit(self) -> list[AuditEvent]:
        """Returns every audit event in the order each occurred."""
        with self._lock:
            return list(self._audit)

    def ack(self, agent: str, notification_id: NotificationId) -> None:
        """Records that the agent finished responding to a notification.

        The cursor advances to the end of the range the notification
        covered. An acknowledgment of a notification no longer outstanding
        changes nothing; one naming a notification never issued to that
        agent raises.
        """
        with self._lock:
            key = (agent, notification_id)
            outstanding = self._outstanding.pop(key, None)
            if outstanding is None:
                if key in self._issued:
                    return
                raise UnknownNotificationError(
                    f"no notification {notification_id} was issued to {agent!r}"
                )
            outstanding.deadline_call.cancel()
            state = self._agents[agent]
            state.cursor = max(state.cursor, outstanding.to_sequence)
            self._audit.append(
                NotificationAcknowledged(
                    at=self._clock.now(), agent=agent, notification_id=notification_id
                )
            )

    def extend(self, agent: str, notification_id: NotificationId) -> datetime | None:
        """Grants the agent a new acknowledgment deadline for a notification.

        Returns the new deadline, or nothing when the notification is no
        longer outstanding. An identifier never issued to that agent raises.
        """
        with self._lock:
            key = (agent, notification_id)
            outstanding = self._outstanding.get(key)
            if outstanding is None:
                if key in self._issued:
                    return None
                raise UnknownNotificationError(
                    f"no notification {notification_id} was issued to {agent!r}"
                )
            outstanding.deadline_call.cancel()
            now = self._clock.now()
            new_deadline = now + self._agents[agent].declaration.acknowledgment_deadline
            outstanding.generation += 1
            outstanding.deadline_call = self._clock.call_at(
                new_deadline,
                partial(self._deadline_passed, key, outstanding.generation),
            )
            self._audit.append(
                DeadlineExtended(
                    at=now,
                    agent=agent,
                    notification_id=notification_id,
                    new_deadline=new_deadline,
                )
            )
            return new_deadline

    def _note_register_change(self, register: str, writer: str) -> list[_Delivery]:
        # Callers hold self._lock. Returns the deliveries the caller makes
        # after releasing it.
        now = self._clock.now()
        window = self._batch_windows[register]
        deliveries: list[_Delivery] = []
        for state in self._agents.values():
            if state.declaration.name == writer or state.capped:
                continue
            due = now + window
            existing = state.pending.get(register)
            state.pending[register] = due if existing is None else min(existing, due)
            earliest = min(state.pending.values())
            if earliest <= now:
                deliveries.append(self._dispatch(state, now))
            elif state.window_due is None or earliest < state.window_due:
                if state.window_call is not None:
                    state.window_call.cancel()
                name = state.declaration.name
                state.window_due = earliest
                state.window_generation += 1
                state.window_call = self._clock.call_at(
                    earliest, partial(self._close_window, name, state.window_generation)
                )
        return deliveries

    def _dispatch(self, state: _AgentState, now: datetime) -> _Delivery:
        # Callers hold self._lock.
        if state.window_call is not None:
            state.window_call.cancel()
            state.window_call = None
            state.window_due = None
            state.window_generation += 1
        registers = frozenset(state.pending)
        state.pending.clear()
        notification_id = NotificationId(self._next_notification_id)
        self._next_notification_id += 1
        deadline = now + state.declaration.acknowledgment_deadline
        notification = Notification(
            notification_id=notification_id,
            agent=state.declaration.name,
            from_sequence=state.cursor + 1,
            to_sequence=self._last_sequence,
            registers=registers,
            deadline=deadline,
        )
        key = (state.declaration.name, notification_id)
        self._issued.add(key)
        self._outstanding[key] = _Outstanding(
            deadline_call=self._clock.call_at(
                deadline, partial(self._deadline_passed, key, 0)
            ),
            to_sequence=self._last_sequence,
        )
        state.wake_count += 1
        self._audit.append(NotificationDispatched(at=now, notification=notification))
        if state.wake_count == state.declaration.wake_cap:
            state.capped = True
            self._audit.append(WakeCapReached(at=now, agent=state.declaration.name))
        return (state.declaration.notify, notification)

    def _close_window(self, agent_name: str, generation: int) -> None:
        # A cancelled timer whose call already started still runs; the
        # generation identifies the armed window, so a stale call changes
        # nothing.
        deliveries: list[_Delivery] = []
        with self._lock:
            state = self._agents.get(agent_name)
            if state is None or state.window_generation != generation:
                return
            state.window_call = None
            state.window_due = None
            state.window_generation += 1
            if state.pending and not state.capped:
                deliveries.append(self._dispatch(state, self._clock.now()))
        self._deliver(deliveries)

    def _deadline_passed(
        self, key: tuple[str, NotificationId], generation: int
    ) -> None:
        # The generation identifies the armed deadline; a stale call from a
        # deadline that extend replaced changes nothing.
        with self._lock:
            outstanding = self._outstanding.get(key)
            if outstanding is None or outstanding.generation != generation:
                return
            del self._outstanding[key]
            agent, notification_id = key
            self._presumed_failed.add(agent)
            self._audit.append(
                PresumedFailed(
                    at=self._clock.now(), agent=agent, notification_id=notification_id
                )
            )

    def _deliver(self, deliveries: list[_Delivery]) -> None:
        # One flat drain loop per thread: a callback that writes a register
        # enqueues the resulting deliveries and returns, so chained wakes
        # cost queue entries, not stack frames.
        self._delivery_queue.extend(deliveries)
        if getattr(self._delivering, "active", False):
            return
        self._delivering.active = True
        try:
            while True:
                try:
                    notify, notification = self._delivery_queue.popleft()
                except IndexError:
                    return
                # The callback is application code at the library's
                # boundary. An agent whose delivery raised never
                # acknowledges, so the deadline machinery records its
                # failure; raising would abort the rest of the batch and
                # reach an unrelated writer.
                with suppress(Exception):
                    notify(notification)
        finally:
            self._delivering.active = False

    def _refuse_region(
        self, writer: str, region: str, expected: _RegionKind
    ) -> Rejected | None:
        with self._lock:
            kind = self._kinds.get(region)
        if kind is None:
            return self._reject(
                writer,
                region,
                RejectionCause.UNDECLARED_REGION,
                f"no region is declared with the name {region!r}",
            )
        if kind is not expected:
            if expected is _RegionKind.LEVEL:
                raise RegionKindError(
                    f"{region!r} names a register, and this operation takes a level"
                )
            raise RegionKindError(
                f"{region!r} names a level, and this operation takes a register"
            )
        return None

    def _reject(
        self, writer: str, region: str, cause: RejectionCause, reason: str
    ) -> Rejected:
        with self._lock:
            self._audit.append(
                WriteRejected(
                    at=self._clock.now(),
                    writer=writer,
                    region=region,
                    cause=cause,
                    reason=reason,
                )
            )
        return Rejected(cause=cause, reason=reason)
