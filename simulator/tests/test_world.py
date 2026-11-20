"""Milestones 2-3: world building and invariants (CLAUDE.md 4.2, 4.3)."""

import pytest

from simulator.engine import Engine

pytestmark = pytest.mark.skip(reason="TODO milestone 2: delete this line once world.py is implemented")


def test_world_built_from_baseline(engine: Engine) -> None:
    """3 hospitals, 4 ambulances all AVAILABLE at base; bed ids like H1-ICU-01."""


def test_initial_occupancy_matches_scenario(engine: Engine) -> None:
    """H1-ICU has round(10 * 0.8) = 8 OCCUPIED beds, each with a SIM-PT- patient ref."""


def test_bed_transitions_reject_invalid_moves() -> None:
    """occupy() on an OCCUPIED bed and release() on a FREE bed raise InvalidTransition."""


def test_ambulance_transitions_follow_allowed_graph() -> None:
    """e.g. AVAILABLE -> TRANSPORTING raises InvalidTransition."""


def test_invariants_hold_every_tick_long_run(engine: Engine) -> None:
    """Inject a few emergency calls, step 6 sim hours one tick at a time, and assert
    engine.require_world().check_invariants() == [] after every tick."""
