"""Milestone 8: fault injection (CLAUDE.md 6, 10)."""

import pytest
from fastapi.testclient import TestClient

from simulator.engine import Engine
from simulator.sinks import InMemorySink

pytestmark = pytest.mark.skip(reason="TODO milestone 8")


def test_his_feed_down(client: TestClient, engine: Engine, adt_sink: InMemorySink) -> None:
    """his_feed_down H1 for 30 min: census 503, no ADT for H1 during it (beds still change),
    census 200 again after."""


def test_telemetry_offline(client: TestClient, engine: Engine, ambulance_sink: InMemorySink) -> None:
    """telemetry_offline A1 2 min: no A1 PositionUpdates, updatedAt goes stale (> 60 s),
    crew message -> QUEUED and is answered after telemetry returns."""


def test_beds_out_of_service(engine: Engine) -> None:
    """beds_out_of_service H3 ICU 3: 3 previously FREE beds are OUT_OF_SERVICE, census shows it."""


def test_mass_casualty_dispatches_as_ambulances_free_up(engine: Engine) -> None:
    """15 casualties, 4 ambulances: all 4 dispatched, the rest wait; incident drains over time."""
