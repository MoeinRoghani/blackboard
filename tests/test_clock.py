"""One injected clock reads the current instant and arms calls at later ones."""

import threading
from datetime import UTC, datetime, timedelta

import pytest

from blackboard import ManualClock, SystemClock

START = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


class TestManualClock:
    def test_now_starts_at_the_given_instant(self) -> None:
        clock = ManualClock(start=START)
        assert clock.now() == START

    def test_advance_moves_now(self) -> None:
        clock = ManualClock(start=START)
        clock.advance(timedelta(seconds=30))
        assert clock.now() == START + timedelta(seconds=30)

    def test_a_due_call_fires_during_advance(self) -> None:
        clock = ManualClock(start=START)
        fired: list[datetime] = []
        clock.call_at(START + timedelta(seconds=10), lambda: fired.append(clock.now()))
        clock.advance(timedelta(seconds=9))
        assert fired == []
        clock.advance(timedelta(seconds=1))
        assert fired == [START + timedelta(seconds=10)]

    def test_calls_fire_in_due_order_with_ties_in_arming_order(self) -> None:
        clock = ManualClock(start=START)
        fired: list[str] = []
        clock.call_at(START + timedelta(seconds=20), lambda: fired.append("late"))
        clock.call_at(START + timedelta(seconds=10), lambda: fired.append("early"))
        clock.call_at(START + timedelta(seconds=10), lambda: fired.append("tied"))
        clock.advance(timedelta(seconds=30))
        assert fired == ["early", "tied", "late"]

    def test_a_call_armed_during_an_advance_fires_inside_it_when_due(self) -> None:
        clock = ManualClock(start=START)
        fired: list[str] = []

        def arm_second() -> None:
            fired.append("first")
            clock.call_at(START + timedelta(seconds=15), lambda: fired.append("second"))

        clock.call_at(START + timedelta(seconds=10), arm_second)
        clock.advance(timedelta(seconds=30))
        assert fired == ["first", "second"]

    def test_a_call_armed_at_or_before_now_fires_on_a_zero_advance(self) -> None:
        clock = ManualClock(start=START)
        fired: list[str] = []
        clock.call_at(START, lambda: fired.append("due"))
        assert fired == []
        clock.advance(timedelta(0))
        assert fired == ["due"]

    def test_a_cancelled_call_never_fires(self) -> None:
        clock = ManualClock(start=START)
        fired: list[str] = []
        scheduled = clock.call_at(
            START + timedelta(seconds=10), lambda: fired.append("x")
        )
        scheduled.cancel()
        clock.advance(timedelta(seconds=60))
        assert fired == []

    def test_time_does_not_move_backward(self) -> None:
        clock = ManualClock(start=START)
        with pytest.raises(ValueError, match="backward"):
            clock.advance(timedelta(seconds=-1))

    def test_a_fired_call_advancing_past_the_target_leaves_time_there(self) -> None:
        clock = ManualClock(start=START)
        observed: list[datetime] = []

        def advance_further() -> None:
            clock.advance(timedelta(seconds=100))
            observed.append(clock.now())

        clock.call_at(START + timedelta(seconds=5), advance_further)
        clock.advance(timedelta(seconds=10))
        assert observed == [START + timedelta(seconds=105)]
        assert clock.now() == START + timedelta(seconds=105)


class TestSystemClock:
    def test_now_is_a_timezone_aware_utc_instant(self) -> None:
        now = SystemClock().now()
        assert now.tzinfo is not None
        assert now.utcoffset() == timedelta(0)

    def test_an_armed_call_fires(self) -> None:
        clock = SystemClock()
        fired = threading.Event()
        clock.call_at(clock.now() + timedelta(milliseconds=20), fired.set)
        assert fired.wait(timeout=5)

    def test_a_cancelled_call_does_not_fire(self) -> None:
        clock = SystemClock()
        fired = threading.Event()
        scheduled = clock.call_at(clock.now() + timedelta(milliseconds=50), fired.set)
        scheduled.cancel()
        assert not fired.wait(timeout=0.2)
