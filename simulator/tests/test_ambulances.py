"""Milestone 4: movement, statuses, emergency_call, PositionUpdate (CLAUDE.md 4.5, 5.2)."""

import pytest
from fastapi.testclient import TestClient

from simulator.engine import Engine
from simulator.sinks import InMemorySink

pytestmark = pytest.mark.skip(reason="TODO milestone 4")


def test_emergency_call_dispatches_nearest_available(engine: Engine) -> None:
    """Inject a call next to A3's base: A3 goes EN_ROUTE_TO_SCENE, others stay AVAILABLE."""


def test_ambulance_reaches_scene_then_awaits_destination(engine: Engine) -> None:
    """run_until AT_SCENE, then within 15 sim minutes AWAITING_DESTINATION with a patient_ref."""


def test_position_update_every_tick(engine: Engine, ambulance_sink: InMemorySink) -> None:
    """step(5) -> 5 x 4 PositionUpdates, timestamps equal to sim time, key = vehicleId."""


def test_tracking_endpoints(client: TestClient) -> None:
    """GET /tracking/vehicles lists 4; GET /tracking/vehicles/A1 ok; unknown -> 404."""
