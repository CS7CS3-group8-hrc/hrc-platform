"""Pure geometry helpers (CLAUDE.md Sections 4.5 and 5.3).

Everything here is a pure function of its inputs: no RNG, no clock, no state.
That makes this the easiest module to start with and to unit-test.
"""

from __future__ import annotations

EARTH_RADIUS_KM = 6371.0088
ARRIVAL_RADIUS_KM = 0.05  # "within 50 m" counts as arrived
PATH_SAMPLE_KM = 0.2  # Route.path is sampled every ~200 m

LatLonPair = tuple[float, float]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres.

    TODO:
      - convert degrees to radians (math.radians)
      - a = sin²(Δφ/2) + cos φ1 · cos φ2 · sin²(Δλ/2)
      - return 2 · R · asin(√a)
    Sanity check: Dublin Spire (53.3498, -6.2603) to Dublin Airport (53.4264, -6.2499) ≈ 8.5 km.
    """
    raise NotImplementedError


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compass heading from point 1 towards point 2, in degrees [0, 360). 0 = north, 90 = east.

    TODO:
      - θ = atan2(sin Δλ · cos φ2, cos φ1 · sin φ2 − sin φ1 · cos φ2 · cos Δλ)
      - return (degrees(θ) + 360) % 360
    """
    raise NotImplementedError


def interpolate(a: LatLonPair, b: LatLonPair, fraction: float) -> LatLonPair:
    """Point a `fraction` (0..1) of the way from a to b.

    Linear interpolation of lat/lon is fine at city scale (a few km); no need for slerp.
    TODO: clamp fraction to [0, 1] and lerp each coordinate.
    """
    raise NotImplementedError


def move_towards(
    current: LatLonPair, target: LatLonPair, step_km: float
) -> tuple[LatLonPair, bool]:
    """Advance from `current` towards `target` by `step_km` along the straight line.

    Returns (new_position, arrived). `arrived` is True when the remaining distance after the
    step is within ARRIVAL_RADIUS_KM, or the step would overshoot; in that case snap to `target`.

    TODO:
      - remaining = haversine_km(current, target)
      - if remaining - step_km <= ARRIVAL_RADIUS_KM: return target, True
      - else: return interpolate(current, target, step_km / remaining), False
    """
    raise NotImplementedError


def sample_path(a: LatLonPair, b: LatLonPair, every_km: float = PATH_SAMPLE_KM) -> list[LatLonPair]:
    """Straight-line path from a to b, sampled every ~`every_km`. Includes both endpoints.

    TODO:
      - n = max(1, ceil(distance / every_km))
      - return [interpolate(a, b, i / n) for i in range(n + 1)]
    """
    raise NotImplementedError


def travel_duration_seconds(
    distance_km: float,
    speed_kmh: float,
    road_distance_factor: float,
    congestion_factor: float = 1.0,
) -> int:
    """Estimated duration (CLAUDE.md 5.3):

        distance × road_distance_factor ÷ speed × congestion_factor   (in hours → seconds)

    TODO: compute and round to an int number of seconds.
    """
    raise NotImplementedError
