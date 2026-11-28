"""Milestone 1."""

from fastapi.testclient import TestClient


def test_health(bare_client: TestClient) -> None:
    resp = bare_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_builds(bare_client: TestClient) -> None:
    schema = bare_client.get("/openapi.json").json()
    paths = set(schema["paths"])
    for expected in [
        "/his/{hospital_id}/census",
        "/tracking/vehicles",
        "/tracking/vehicles/{vehicle_id}",
        "/tracking/vehicles/{vehicle_id}/messages",
        "/tracking/messages/{message_id}/response",
        "/travel/times",
        "/travel/route",
        "/travel/conditions/{area_id}",
        "/sim/scenario/load",
        "/sim/start",
        "/sim/pause",
        "/sim/reset",
        "/sim/speed",
        "/sim/inject",
        "/sim/state",
        "/health",
        "/metrics",
    ]:
        assert expected in paths, expected
