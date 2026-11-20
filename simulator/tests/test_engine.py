"""Milestone 2: clock, queue, speed, pause (CLAUDE.md 4.1)."""

import pytest

from simulator.engine import Engine

pytestmark = pytest.mark.skip(reason="TODO milestone 2")


def test_loads_stopped_at_start_time(engine: Engine) -> None:
    """status STOPPED, sim_time == scenario.start_time, tick_count 0."""


def test_step_advances_one_second(engine: Engine) -> None:
    """step(10) moves sim_time by exactly 10 s."""


def test_scheduled_events_run_in_time_then_insertion_order(engine: Engine) -> None:
    """Two events at the same time run in the order they were scheduled; an earlier one first."""


def test_start_pause_reset(engine: Engine) -> None:
    """start -> RUNNING, pause -> PAUSED, reset -> STOPPED and sim_time back to start."""


def test_speed_must_be_positive(engine: Engine) -> None:
    """set_speed(0) raises ValueError."""
