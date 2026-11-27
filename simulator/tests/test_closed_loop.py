"""Milestone 6: the thin slice end to end, driven through the HTTP API (CLAUDE.md 4.6, 10)."""

import pytest
from fastapi.testclient import TestClient

from simulator.engine import Engine
from simulator.sinks import InMemorySink

pytestmark = pytest.mark.skip(reason="TODO milestone 6")


def test_closed_loop(
    client: TestClient, engine: Engine, adt_sink: InMemorySink, ambulance_sink: InMemorySink
) -> None:
    """
    1. POST /sim/inject emergency_call
    2. step until some vehicle is AWAITING_DESTINATION (check via GET /tracking/vehicles)
    3. POST /tracking/vehicles/{id}/messages {type: DESTINATION, hospitalId: H2,
       placementId: PL-TEST, department: ED} -> DELIVERED
    4. GET /tracking/messages/{messageId}/response -> 404, then step 20 s -> ACKNOWLEDGED
    5. a CrewResponse event is on ambulance_sink
    6. step until AT_HOSPITAL, then past the admission delay
    7. adt_sink has an A01 at H2/ED with placementId == "PL-TEST"; H2 ED occupied count +1
    """


def test_crew_reject_next(client: TestClient, engine: Engine) -> None:
    """Arm crew_reject_next for the vehicle: response REJECTED with the reason; vehicle stays
    AWAITING_DESTINATION; the following message is ACKNOWLEDGED."""


def test_arrival_no_free_bed(engine: Engine, adt_sink: InMemorySink) -> None:
    """Fill H2 ED, complete a transport there: no A01, counters['arrival_no_free_bed'] == 1."""


def test_reroute_while_transporting(client: TestClient, engine: Engine) -> None:
    """REROUTE to H3 while TRANSPORTING to H2 -> after ACK, destination is H3 and it arrives there."""
