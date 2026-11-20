"""geo.py: real assertions; these fail until you implement geo.py."""

import pytest

from simulator import geo

SPIRE = (53.3498, -6.2603)
AIRPORT = (53.4264, -6.2499)


def test_haversine_known_distance() -> None:
    assert geo.haversine_km(*SPIRE, *AIRPORT) == pytest.approx(8.55, abs=0.1)


def test_haversine_zero() -> None:
    assert geo.haversine_km(*SPIRE, *SPIRE) == 0.0


@pytest.mark.parametrize(
    ("target", "expected"),
    [((54.0, 0.0), 0.0), ((53.0, 1.0), 90.0), ((52.0, 0.0), 180.0), ((53.0, -1.0), 270.0)],
)
def test_bearing_cardinal_directions(target: tuple[float, float], expected: float) -> None:
    assert geo.initial_bearing_deg(53.0, 0.0, *target) == pytest.approx(expected, abs=0.5)


def test_move_towards_reaches_target_in_expected_ticks() -> None:
    """At 60 km/h one tick (1 s) covers 1/60 km. Spire → airport ≈ 8.55 km ≈ 513 ticks."""
    step_km = 60 / 3600
    pos, arrived, ticks = SPIRE, False, 0
    while not arrived:
        pos, arrived = geo.move_towards(pos, AIRPORT, step_km)
        ticks += 1
        assert ticks < 1000
    assert pos == AIRPORT
    expected = geo.haversine_km(*SPIRE, *AIRPORT) / step_km
    assert abs(ticks - expected) <= 4  # 50 m arrival radius ≈ 3 ticks early


def test_sample_path_spacing() -> None:
    path = geo.sample_path(SPIRE, AIRPORT)
    assert path[0] == SPIRE and path[-1] == AIRPORT
    for a, b in zip(path, path[1:], strict=False):
        assert geo.haversine_km(*a, *b) <= geo.PATH_SAMPLE_KM + 1e-6


def test_travel_duration() -> None:
    # 10 km × 1.3 / 60 km/h = 13 min = 780 s; doubled by congestion 2.0
    assert geo.travel_duration_seconds(10, 60, 1.3) == 780
    assert geo.travel_duration_seconds(10, 60, 1.3, congestion_factor=2.0) == 1560
