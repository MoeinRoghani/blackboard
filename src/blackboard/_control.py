"""The write path of the control component.

A write made through the control component passes the application's
admission rule before the board sequences it. The rule sees the proposed
write with a read handle on the board and returns accept or a reasoned
rejection. An admitted level write is sequenced and audited. An admitted
register write may still fail with a conflict, which returns to the writer
unaudited. A rejected write returns its reason to the writer, never reaches
the board, and is audited without a sequence number.

The rule runs without the control component's lock, so two writes judged at
the same moment are both judged against the board as it was before either
landed. A
register write closes that window with its expected version; a level write
does not, so a rule refusing duplicates bounds concurrent duplicates rather
than preventing them.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, TypeAlias

from blackboard._board import (
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
from blackboard._clock import Clock


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


AuditEvent: TypeAlias = WriteAccepted | WriteRejected


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
        self._audit: list[AuditEvent] = []
        self._in_flight = 0
        for region in regions:
            self.declare(region)

    @property
    def reader(self) -> BoardReader:
        """The board's read side. Reads bypass the control component entirely."""
        return self._board

    def declare(self, region: Level | Register) -> None:
        """Creates a region on the board and records its kind."""
        self._board.declare(region)
        with self._lock:
            self._kinds[region.name] = (
                _RegionKind.LEVEL if isinstance(region, Level) else _RegionKind.REGISTER
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
            with self._lock:
                result = self._board.set(register, value, expected_version)
                if isinstance(result, Written):
                    self._audit.append(
                        WriteAccepted(
                            at=self._clock.now(),
                            writer=writer,
                            region=register,
                            sequence=result.sequence,
                        )
                    )
            return result
        finally:
            with self._lock:
                self._in_flight -= 1

    def read_audit(self) -> list[AuditEvent]:
        """Returns every audit event in the order each occurred."""
        with self._lock:
            return list(self._audit)

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
