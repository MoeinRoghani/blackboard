"""A model is created from six inputs, and the seed's wakes activate the agents."""

import threading
from datetime import UTC, datetime, timedelta

import pytest

from blackboard import (
    Accepted,
    Agent,
    BoardReader,
    BudgetExhausted,
    BudgetKind,
    Complete,
    DuplicateAgentError,
    Level,
    ManualClock,
    Model,
    Notification,
    Register,
    RegisterSeeded,
    RunBudgets,
    SeedError,
    TerminationDecision,
    WakeCapReached,
    create_model,
)

START = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
DEADLINE = timedelta(minutes=5)

BUDGETS = RunBudgets(
    wall_clock=timedelta(hours=1), total_writes=1000, total_notifications=1000
)


def keep_open(reader: BoardReader) -> TerminationDecision:
    return TerminationDecision.CONTINUE


class TestCreateModel:
    def test_the_seed_wakes_every_agent_once_and_the_run_settles(self) -> None:
        # The seed dispatches inside create_model, before the model exists,
        # so a callback records its wake and the agent acts afterward on its
        # own execution.
        first: list[Notification] = []
        second: list[Notification] = []

        clock = ManualClock(start=START)
        model = create_model(
            regions=[Level("application"), Register("window"), Register("service")],
            agents=[
                Agent(
                    name="ocp",
                    acknowledgment_deadline=DEADLINE,
                    wake_cap=100,
                    notify=first.append,
                ),
                Agent(
                    name="git",
                    acknowledgment_deadline=DEADLINE,
                    wake_cap=100,
                    notify=second.append,
                ),
            ],
            seed={"window": ("t1", "t2"), "service": "checkout"},
            budgets=BUDGETS,
            clock=clock,
        )
        assert len(first) == 1
        assert len(second) == 1
        assert first[0].registers == frozenset({"window", "service"})
        assert first[0].from_sequence == 1
        assert first[0].to_sequence == 2
        assert model.control.outcome() is None
        model.control.ack("ocp", first[0].notification_id)
        model.control.ack("git", second[0].notification_id)
        assert model.control.outcome() == Complete()

    def test_the_seed_names_exactly_the_declared_registers(self) -> None:
        clock = ManualClock(start=START)
        with pytest.raises(SeedError, match="misses"):
            create_model(
                regions=[Register("window"), Register("service")],
                agents=[],
                seed={"window": "w"},
                budgets=BUDGETS,
                clock=clock,
            )
        with pytest.raises(SeedError, match="undeclared"):
            create_model(
                regions=[Register("window")],
                agents=[],
                seed={"window": "w", "unknown": "x"},
                budgets=BUDGETS,
                clock=clock,
            )

    def test_seed_writes_are_audited_and_bypass_the_write_budget(self) -> None:
        clock = ManualClock(start=START)
        model = create_model(
            regions=[Level("application"), Register("window"), Register("service")],
            agents=[],
            seed={"window": "w", "service": "s"},
            termination_predicate=keep_open,
            budgets=RunBudgets(
                wall_clock=timedelta(hours=1),
                total_writes=1,
                total_notifications=1000,
            ),
            clock=clock,
        )
        seeded = [
            event
            for event in model.control.read_audit()
            if isinstance(event, RegisterSeeded)
        ]
        assert [event.register for event in seeded] == ["window", "service"]
        assert all(event.version == 1 for event in seeded)
        assert model.reader.read_register("window").value == "w"
        result = model.control.write("ocp", "application", "fits the budget")
        assert result == Accepted(sequence=3)

    def test_seed_wakes_count_against_the_wake_cap(self) -> None:
        received: list[Notification] = []
        clock = ManualClock(start=START)
        model = create_model(
            regions=[Register("window")],
            agents=[
                Agent(
                    name="ocp",
                    acknowledgment_deadline=DEADLINE,
                    wake_cap=1,
                    notify=received.append,
                )
            ],
            seed={"window": "w"},
            budgets=BUDGETS,
            clock=clock,
        )
        assert len(received) == 1
        assert any(
            isinstance(event, WakeCapReached) for event in model.control.read_audit()
        )
        model.control.set_register("operator", "window", "w2", expected_version=1)
        assert len(received) == 1

    def test_seed_wakes_count_against_the_notification_budget(self) -> None:
        first: list[Notification] = []
        second: list[Notification] = []
        clock = ManualClock(start=START)
        model = create_model(
            regions=[Register("window")],
            agents=[
                Agent(
                    name="a",
                    acknowledgment_deadline=DEADLINE,
                    wake_cap=10,
                    notify=first.append,
                ),
                Agent(
                    name="b",
                    acknowledgment_deadline=DEADLINE,
                    wake_cap=10,
                    notify=second.append,
                ),
            ],
            seed={"window": "w"},
            budgets=RunBudgets(
                wall_clock=timedelta(hours=1),
                total_writes=1000,
                total_notifications=1,
            ),
            clock=clock,
        )
        assert len(first) == 1
        assert second == []
        assert model.control.outcome() == BudgetExhausted(
            budget=BudgetKind.TOTAL_NOTIFICATIONS
        )

    def test_a_model_whose_seed_wakes_no_agent_closes_at_once(self) -> None:
        clock = ManualClock(start=START)
        model = create_model(
            regions=[Register("window")],
            agents=[],
            seed={"window": "w"},
            budgets=BUDGETS,
            clock=clock,
        )
        assert model.control.outcome() == Complete()

    def test_duplicate_agent_names_are_refused(self) -> None:
        clock = ManualClock(start=START)
        recorder: list[Notification] = []
        declaration = Agent(
            name="ocp",
            acknowledgment_deadline=DEADLINE,
            wake_cap=1,
            notify=recorder.append,
        )
        with pytest.raises(DuplicateAgentError):
            create_model(
                regions=[Register("window")],
                agents=[declaration, declaration],
                seed={"window": "w"},
                budgets=BUDGETS,
                clock=clock,
            )


class TestFullCycle:
    def test_a_pipeline_runs_from_seed_to_complete_through_the_public_surface(
        self,
    ) -> None:
        clock = ManualClock(start=START)
        wakes: list[Notification] = []

        model = create_model(
            regions=[Level("platform"), Register("window")],
            agents=[
                Agent(
                    name="ocp",
                    acknowledgment_deadline=DEADLINE,
                    wake_cap=10,
                    notify=wakes.append,
                )
            ],
            seed={"window": ("t1", "t2")},
            budgets=BUDGETS,
            clock=clock,
        )

        # The agent's cycle: read the premises, contribute, acknowledge.
        (wake,) = wakes
        window = model.reader.read_register("window").value
        bundle = {"producer": "ocp", "window": window, "findings": ["oom"]}
        model.control.write("ocp", "platform", bundle)
        model.control.ack("ocp", wake.notification_id)

        assert model.control.outcome() == Complete()
        (contribution,) = model.reader.read_level("platform")
        assert contribution.content == {
            "producer": "ocp",
            "window": ("t1", "t2"),
            "findings": ["oom"],
        }


class TestSystemClockIntegration:
    def test_wait_closed_returns_complete_under_the_default_clock(self) -> None:
        model_holder: list[Model] = []

        def hand_off(notification: Notification) -> None:
            def work() -> None:
                model = model_holder[0]
                model.control.write("ocp", "platform", "bundle")
                model.control.ack("ocp", notification.notification_id)

            threading.Timer(0.03, work).start()

        model = create_model(
            regions=[Level("platform"), Register("window")],
            agents=[
                Agent(
                    name="ocp",
                    acknowledgment_deadline=timedelta(seconds=30),
                    wake_cap=10,
                    notify=hand_off,
                )
            ],
            seed={"window": "w"},
            budgets=RunBudgets(
                wall_clock=timedelta(minutes=1),
                total_writes=10,
                total_notifications=10,
            ),
        )
        model_holder.append(model)
        outcome = model.control.wait_closed(timeout=timedelta(seconds=10))
        assert outcome == Complete()
        (contribution,) = model.reader.read_level("platform")
        assert contribution.content == "bundle"


class _InertHandle:
    def cancel(self) -> None:
        """The call already ran; cancellation changes nothing."""


class EagerClock:
    """A clock whose armed calls fire the moment they are armed.

    It stands in for the race in which the wall-clock budget expires while
    the run is still opening.
    """

    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def call_at(self, when: datetime, call: object) -> _InertHandle:
        call()  # type: ignore[operator]  # the armed call takes no arguments
        return _InertHandle()


class TestOpeningRaces:
    def test_a_wall_clock_expiring_while_opening_returns_a_closed_model(self) -> None:
        received: list[Notification] = []
        model = create_model(
            regions=[Register("window")],
            agents=[
                Agent(
                    name="ocp",
                    acknowledgment_deadline=DEADLINE,
                    wake_cap=10,
                    notify=received.append,
                )
            ],
            seed={"window": "w"},
            budgets=BUDGETS,
            clock=EagerClock(start=START),
        )
        assert model.control.outcome() == BudgetExhausted(budget=BudgetKind.WALL_CLOCK)
        assert received == []
        assert not any(
            isinstance(event, RegisterSeeded) for event in model.control.read_audit()
        )
        closing = [
            event
            for event in model.control.read_audit()
            if event.__class__.__name__ == "RunClosed"
        ]
        assert len(closing) == 1


class TestSeedBatchWindows:
    def test_a_windowed_register_delays_the_opening_wake(self) -> None:
        received: list[Notification] = []
        clock = ManualClock(start=START)
        model = create_model(
            regions=[Register("namespace", batch_window=timedelta(seconds=5))],
            agents=[
                Agent(
                    name="ocp",
                    acknowledgment_deadline=DEADLINE,
                    wake_cap=10,
                    notify=received.append,
                )
            ],
            seed={"namespace": ("ns1",)},
            budgets=BUDGETS,
            clock=clock,
        )
        assert received == []
        assert model.control.outcome() is None
        clock.advance(timedelta(seconds=5))
        (wake,) = received
        assert wake.registers == frozenset({"namespace"})
