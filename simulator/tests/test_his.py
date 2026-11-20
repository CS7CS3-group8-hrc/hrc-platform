"""Milestone 3: background ADT and census (CLAUDE.md 4.4, 5.1)."""

import pytest
from fastapi.testclient import TestClient

from simulator.engine import Engine
from simulator.sinks import InMemorySink

pytestmark = pytest.mark.skip(reason="TODO milestone 3")


def test_background_admissions_emit_a01(engine: Engine, adt_sink: InMemorySink) -> None:
    """Run 2 sim hours: some A01 events, each into a bed that's now OCCUPIED."""


def test_discharges_emit_a03(engine: Engine, adt_sink: InMemorySink) -> None:
    """Run 12 sim hours: ED LOS mean 4 h, so A03s appear and free their beds."""


def test_capacity_full_counted_not_invented(engine: Engine) -> None:
    """Fill a ward, force an admission: counters['capacity_full'] increments, no bed overflow."""


def test_census_endpoint(client: TestClient, engine: Engine) -> None:
    """GET /his/H1/census validates as BedCensus; counts match the world; no patientRef in body."""


def test_census_unknown_hospital_404(client: TestClient) -> None:
    """GET /his/NOPE/census -> 404."""
