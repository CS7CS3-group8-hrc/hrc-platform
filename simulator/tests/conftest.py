"""Shared fixtures. Tests never need Kafka or the network: they use InMemorySink and step the
engine directly (CLAUDE.md 10)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from simulator.app import create_app
from simulator.config import SCENARIO_DIR, Settings
from simulator.engine import Engine
from simulator.scenario import load_scenario
from simulator.sinks import InMemorySink


@pytest.fixture
def settings() -> Settings:
    return Settings(sim_scenario="baseline", kafka_bootstrap_servers=None, adt_sink="log")


@pytest.fixture
def ambulance_sink() -> InMemorySink:
    return InMemorySink()


@pytest.fixture
def adt_sink() -> InMemorySink:
    return InMemorySink()


@pytest.fixture
def engine(settings: Settings, ambulance_sink: InMemorySink, adt_sink: InMemorySink) -> Engine:
    """An engine with baseline loaded, STOPPED at startTime. Needs milestone 2."""
    eng = Engine(settings, ambulance_sink, adt_sink)
    eng.load_scenario(load_scenario("baseline", SCENARIO_DIR))
    return eng


@pytest.fixture
def bare_client(settings: Settings) -> Iterator[TestClient]:
    """App with no engine attached (enough for /health and OpenAPI)."""
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def client(settings: Settings, engine: Engine) -> Iterator[TestClient]:
    """App wired to the in-memory `engine` fixture. Tests step `engine` directly between calls."""
    app = create_app(settings)
    with TestClient(app) as c:
        app.state.engine = engine  # overrides whatever the lifespan set up
        yield c
