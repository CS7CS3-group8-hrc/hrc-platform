"""Milestones 2-3: world building and invariants (CLAUDE.md 4.2, 4.3)."""

from datetime import UTC, datetime
from itertools import count
from random import Random

import pytest

from simulator.config import SCENARIO_DIR
from simulator.contracts import AmbulanceStatus, BedStatus, Department
from simulator.engine import Engine
from simulator.scenario import load_scenario
from simulator.world import Bed, InvalidTransition, World, build_ambulance, build_hospital

START = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)
needs_engine = pytest.mark.skip(reason="TODO milestone 2: needs engine.py")


def build_baseline_world(seed: int = 42) -> World:
    scenario = load_scenario("baseline", SCENARIO_DIR)
    refs = count(1)
    return World.from_scenario(scenario, Random(seed), START, lambda: f"SIM-PT-{next(refs):06d}")


def test_world_built_from_baseline() -> None:
    """3 hospitals, 4 ambulances all AVAILABLE at base; bed ids like H1-ICU-01."""
    world = build_baseline_world()
    assert list(world.hospitals) == ["H1", "H2", "H3"]
    assert len(world.ambulances) == 4
    for amb in world.ambulances.values():
        assert amb.status is AmbulanceStatus.AVAILABLE
        assert (amb.lat, amb.lon) == (amb.base_lat, amb.base_lon)
        assert amb.speed_kmh > 0
    icu = world.hospital("H1").wards_in(Department.ICU)[0]
    assert [b.bed_id for b in icu.beds[:2]] == ["H1-ICU-01", "H1-ICU-02"]
    assert icu.beds[-1].bed_id == "H1-ICU-10"


def test_initial_occupancy_matches_scenario() -> None:
    """H1-ICU has round(10 * 0.8) = 8 OCCUPIED beds, each with a SIM-PT- patient ref."""
    world = build_baseline_world()
    icu = world.hospital("H1").wards_in(Department.ICU)[0]
    occupied = icu.beds_with_status(BedStatus.OCCUPIED)
    assert len(occupied) == 8
    for bed in occupied:
        assert bed.patient_ref is not None and bed.patient_ref.startswith("SIM-PT-")
        assert bed.occupied_since == START
    assert world.check_invariants() == []


def test_initial_occupancy_is_deterministic() -> None:
    def occupied_ids(world: World) -> list[str]:
        return [
            b.bed_id
            for h in world.hospitals.values()
            for w in h.wards
            for b in w.beds_with_status(BedStatus.OCCUPIED)
        ]

    assert occupied_ids(build_baseline_world(42)) == occupied_ids(build_baseline_world(42))
    assert occupied_ids(build_baseline_world(42)) != occupied_ids(build_baseline_world(7))


def test_lookup_unknown_ids_raise_key_error() -> None:
    world = build_baseline_world()
    with pytest.raises(KeyError):
        world.hospital("H99")
    with pytest.raises(KeyError):
        world.ambulance("A99")


def test_bed_transitions_reject_invalid_moves() -> None:
    """occupy() on an OCCUPIED bed and release() on a FREE bed raise InvalidTransition."""
    bed = Bed("B-01")
    with pytest.raises(InvalidTransition):
        bed.release()
    bed.occupy("SIM-PT-000001", START)
    with pytest.raises(InvalidTransition):
        bed.occupy("SIM-PT-000002", START)
    with pytest.raises(InvalidTransition):
        bed.mark_out_of_service()
    assert bed.release() == "SIM-PT-000001"
    assert (bed.status, bed.patient_ref, bed.occupied_since) == (BedStatus.FREE, None, None)
    bed.mark_out_of_service()
    with pytest.raises(InvalidTransition):
        bed.occupy("SIM-PT-000003", START)


def test_ambulance_transitions_follow_allowed_graph() -> None:
    """e.g. AVAILABLE -> TRANSPORTING raises InvalidTransition."""
    scenario = load_scenario("baseline", SCENARIO_DIR)
    amb = build_ambulance(scenario.ambulances[0], 60.0)
    hospital = build_hospital(scenario.hospitals[0])

    with pytest.raises(InvalidTransition):
        amb.assign_destination(hospital, Department.ED, None)

    # Full happy-path cycle.
    amb.dispatch_to_scene("INC-1", 53.35, -6.26, "TRAUMA")
    assert (amb.target_lat, amb.target_lon) == (53.35, -6.26)
    amb.arrive_at_scene()
    assert amb.target_lat is None
    amb.load_patient("SIM-PT-000001")
    amb.assign_destination(hospital, Department.ED, "PL-1")
    amb.assign_destination(hospital, Department.ICU, "PL-2")  # REROUTE while transporting
    assert (amb.target_lat, amb.target_lon) == (hospital.lat, hospital.lon)
    amb.arrive_at_hospital()
    assert amb.patient_ref == "SIM-PT-000001"
    assert amb.hand_over_and_return() == "SIM-PT-000001"
    assert amb.patient_ref is None and amb.placement_id is None
    assert (amb.target_lat, amb.target_lon) == (amb.base_lat, amb.base_lon)
    amb.arrive_at_base()
    assert amb.status is AmbulanceStatus.AVAILABLE


def test_census_never_includes_patient_ref() -> None:
    world = build_baseline_world()
    census = world.hospital("H1").to_census(START)
    assert "SIM-PT-" not in census.model_dump_json()
    icu = next(w for w in census.wards if w.ward_id == "H1-ICU")
    assert (icu.total_beds, icu.occupied_beds, icu.out_of_service_beds) == (10, 8, 0)


def test_check_invariants_reports_violations() -> None:
    world = build_baseline_world()
    bed = world.hospital("H1").wards[0].beds_with_status(BedStatus.FREE)[0]
    bed.patient_ref = "SIM-PT-999999"  # FREE bed with a patient: broken on purpose
    world.ambulance("A1").patient_ref = "SIM-PT-888888"  # AVAILABLE with a patient
    violations = world.check_invariants()
    assert any(bed.bed_id in v for v in violations)
    assert any("A1" in v for v in violations)


@needs_engine
def test_invariants_hold_every_tick_long_run(engine: Engine) -> None:
    """Inject a few emergency calls, step 6 sim hours one tick at a time, and assert
    engine.require_world().check_invariants() == [] after every tick."""
