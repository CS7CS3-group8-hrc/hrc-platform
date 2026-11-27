"""Milestone 5: travel-time source (CLAUDE.md 5.3)."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skip(reason="TODO milestone 5")


def test_travel_times_ranked_by_distance(client: TestClient) -> None:
    """POST /travel/times from the city centre to H1, H2, H3: one TravelTime each, source
    SIMULATED_ESTIMATE, durations consistent with geo.travel_duration_seconds."""


def test_route_path_sampled(client: TestClient) -> None:
    """POST /travel/route: path starts at origin, ends at destination, points <= ~200 m apart."""


def test_road_condition_slows_estimates(client: TestClient) -> None:
    """Inject road_condition factor 2.0: duration doubles; GET /travel/conditions/dublin lists it;
    after durationMinutes it's gone."""
