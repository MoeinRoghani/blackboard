"""One injected clock reads the current instant and arms calls at chosen ones.

``SystemClock`` is the default and the only code in the library that reads
the operating system clock. ``ManualClock`` moves only through ``advance``,
so a test observes armed calls firing without waiting. Instants are
timezone-aware UTC ``datetime`` values and durations are ``timedelta``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol


class ScheduledCall(Protocol):
    """A call armed on a clock, cancellable until it fires."""

    def cancel(self) -> None:
        """Prevents the call from firing. Cancelling a fired call changes nothing."""


class Clock(Protocol):
    """Reads the current instant and arms calls to fire at chosen instants."""

    def now(self) -> datetime:
        """Returns the current instant, timezone-aware in UTC."""
        ...

    def call_at(self, when: datetime, call: Callable[[], None]) -> ScheduledCall:
        """Arms a call to fire at an instant and returns its cancellation handle."""
        ...


class SystemClock:
    """The default clock, backed by the operating system."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def call_at(self, when: datetime, call: Callable[[], None]) -> ScheduledCall:
        delay = (when - self.now()).total_seconds()
        timer = threading.Timer(max(delay, 0.0), call)
        timer.daemon = True
        timer.start()
        return timer


@dataclass
class _ManualScheduledCall:
    when: datetime
    order: int
    call: Callable[[], None]
    cancelled: bool = field(default=False)

    def cancel(self) -> None:
        self.cancelled = True


class ManualClock:
    """A deterministic clock for tests; time moves only through ``advance``."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start if start is not None else datetime(1970, 1, 1, tzinfo=UTC)
        self._scheduled: list[_ManualScheduledCall] = []
        self._armed = 0
        self._lock = threading.Lock()

    def now(self) -> datetime:
        with self._lock:
            return self._now

    def call_at(self, when: datetime, call: Callable[[], None]) -> ScheduledCall:
        with self._lock:
            scheduled = _ManualScheduledCall(when=when, order=self._armed, call=call)
            self._armed += 1
            self._scheduled.append(scheduled)
            return scheduled

    def advance(self, delta: timedelta) -> None:
        """Moves time forward and fires every due call on the calling thread.

        Calls fire in due order; ties fire in arming order. A call armed
        during the advance fires inside it when its instant falls at or
        before the target. A call armed at or before the current instant
        fires on the next advance, a zero advance included. A fired call may
        itself advance the clock; the outer advance never moves time back
        below where an inner one left it.
        """
        if delta < timedelta(0):
            raise ValueError("time does not move backward")
        with self._lock:
            target = self._now + delta
        while True:
            with self._lock:
                self._scheduled = [s for s in self._scheduled if not s.cancelled]
                due = [s for s in self._scheduled if s.when <= target]
                if not due:
                    self._now = max(self._now, target)
                    return
                due.sort(key=lambda s: (s.when, s.order))
                head = due[0]
                self._scheduled.remove(head)
                self._now = max(self._now, head.when)
            head.call()
