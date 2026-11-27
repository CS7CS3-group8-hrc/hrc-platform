"""Milestone 2: clock, queue, speed, pause (CLAUDE.md 4.1)."""

from datetime import timedelta

import pytest

from simulator.contracts import SimStatus
from simulator.engine import Engine
from simulator.world import InvalidTransition

# The `engine` fixture loads baseline, and reset() schedules background admissions and
# initial discharges, so these need the HIS handlers in processes.py (milestone 3).
pytestmark = pytest.mark.skip(reason="TODO: needs processes.py HIS handlers to load a scenario")


def test_loads_stopped_at_start_time(engine: Engine) -> None:
    """status STOPPED, sim_time == scenario.start_time, tick_count 0."""
    assert engine.scenario is not None
    assert engine.status is SimStatus.STOPPED
    assert engine.sim_time == engine.scenario.start_time
    assert engine.tick_count == 0


def test_step_advances_one_second(engine: Engine) -> None:
    """step(10) moves sim_time by exactly 10 s."""
    start = engine.sim_time
    engine.step(10)
    assert engine.sim_time == start + timedelta(seconds=10)
    assert engine.tick_count == 10


def test_scheduled_events_run_in_time_then_insertion_order(engine: Engine) -> None:
    """Two events at the same time run in the order they were scheduled; an earlier one first."""
    order: list[str] = []
    engine.schedule_in(5, "b", lambda: order.append("b"))
    engine.schedule_in(5, "c", lambda: order.append("c"))
    engine.schedule_in(2, "a", lambda: order.append("a"))
    engine.schedule_in(3, "cancelled", lambda: order.append("cancelled")).cancelled = True
    # An action that schedules another for "now" is picked up in the same tick.
    engine.schedule_in(
        4, "chain", lambda: engine.schedule_in(0, "now", lambda: order.append("now"))
    )
    engine.step(5)
    assert order == ["a", "now", "b", "c"]


def test_start_pause_reset(engine: Engine) -> None:
    """start -> RUNNING, pause -> PAUSED, reset -> STOPPED and sim_time back to start."""
    start = engine.sim_time
    with pytest.raises(InvalidTransition):
        engine.pause()  # nothing to pause while STOPPED
    engine.start()
    assert engine.status is SimStatus.RUNNING
    engine.pause()
    assert engine.status is SimStatus.PAUSED
    engine.step(30)
    engine.reset()
    assert engine.status is SimStatus.STOPPED
    assert engine.sim_time == start
    assert engine.tick_count == 0


def test_speed_must_be_positive(engine: Engine) -> None:
    """set_speed(0) raises ValueError."""
    with pytest.raises(ValueError):
        engine.set_speed(0)
    with pytest.raises(ValueError):
        engine.set_speed(float("nan"))
    engine.set_speed(10)
    engine.reset()
    assert engine.speed == 10  # a runtime setting, kept across reset
