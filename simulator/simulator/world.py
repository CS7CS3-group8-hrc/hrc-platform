"""World state and state transitions (CLAUDE.md Sections 4.2 and 4.3).

These classes hold state and enforce valid transitions. They do NOT emit events, use the RNG,
or know about time beyond the `at` values passed in. The engine decides *when* things happen;
the world decides *whether they are allowed*.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from random import Random

from simulator.contracts import (
    AmbulanceState,
    AmbulanceStatus,
    BedCensus,
    BedStatus,
    Department,
    HospitalState,
    VehicleStatus,
)
from simulator.scenario import AmbulanceSpec, HospitalSpec, Scenario

# Mints the next synthetic patient ref, e.g. "SIM-PT-000123". Owned by the engine.
PatientRefFn = Callable[[], str]


class InvalidTransition(Exception):
    """Raised when a state change is not allowed from the current state."""


# --------------------------------------------------------------------------- beds and wards


@dataclass
class Bed:
    bed_id: str
    status: BedStatus = BedStatus.FREE
    patient_ref: str | None = None
    occupied_since: datetime | None = None

    def occupy(self, patient_ref: str, at: datetime) -> None:
        """FREE → OCCUPIED. TODO: raise InvalidTransition unless FREE; set patient_ref, occupied_since."""
        raise NotImplementedError

    def release(self) -> str:
        """OCCUPIED → FREE. Returns the patient_ref that left.

        TODO: raise InvalidTransition unless OCCUPIED; clear patient_ref and occupied_since.
        """
        raise NotImplementedError

    def mark_out_of_service(self) -> None:
        """FREE → OUT_OF_SERVICE. TODO: raise InvalidTransition unless FREE."""
        raise NotImplementedError


@dataclass
class Ward:
    ward_id: str
    department: Department
    beds: list[Bed]

    @property
    def total_beds(self) -> int:
        return len(self.beds)

    def beds_with_status(self, status: BedStatus) -> list[Bed]:
        """TODO: list of beds in this ward with the given status (keep list order: determinism)."""
        raise NotImplementedError

    def find_patient(self, patient_ref: str) -> Bed | None:
        """TODO: the bed holding this patient, or None."""
        raise NotImplementedError


@dataclass
class Hospital:
    hospital_id: str
    name: str
    lat: float
    lon: float
    wards: list[Ward]
    his_feed_online: bool = True

    def wards_in(self, department: Department) -> list[Ward]:
        """TODO: all wards of this department (a hospital may have more than one)."""
        raise NotImplementedError

    def free_beds_in(self, department: Department) -> list[tuple[Ward, Bed]]:
        """TODO: every FREE bed in that department, paired with its ward, in stable order."""
        raise NotImplementedError

    def find_patient(self, patient_ref: str) -> tuple[Ward, Bed] | None:
        """TODO: locate a patient anywhere in this hospital."""
        raise NotImplementedError

    def to_census(self, as_of: datetime) -> BedCensus:
        """Build the HIS census (CLAUDE.md 5.1). MUST NOT include patientRef.

        TODO: one WardCensus per ward with total/occupied/out-of-service counts and BedSummary list.
        """
        raise NotImplementedError

    def to_state(self) -> HospitalState:
        """Full state for /sim/state (includes patientRef). TODO."""
        raise NotImplementedError


# --------------------------------------------------------------------------- ambulances


# Allowed status transitions. Use this in Ambulance._transition.
ALLOWED_TRANSITIONS: dict[AmbulanceStatus, set[AmbulanceStatus]] = {
    AmbulanceStatus.AVAILABLE: {AmbulanceStatus.EN_ROUTE_TO_SCENE},
    AmbulanceStatus.EN_ROUTE_TO_SCENE: {AmbulanceStatus.AT_SCENE},
    AmbulanceStatus.AT_SCENE: {AmbulanceStatus.AWAITING_DESTINATION},
    AmbulanceStatus.AWAITING_DESTINATION: {AmbulanceStatus.TRANSPORTING},
    AmbulanceStatus.TRANSPORTING: {AmbulanceStatus.TRANSPORTING, AmbulanceStatus.AT_HOSPITAL},
    AmbulanceStatus.AT_HOSPITAL: {AmbulanceStatus.RETURNING},
    AmbulanceStatus.RETURNING: {AmbulanceStatus.AVAILABLE, AmbulanceStatus.EN_ROUTE_TO_SCENE},
}

# Statuses in which the ambulance moves each tick towards (target_lat, target_lon).
MOVING_STATUSES = {
    AmbulanceStatus.EN_ROUTE_TO_SCENE,
    AmbulanceStatus.TRANSPORTING,
    AmbulanceStatus.RETURNING,
}

# Statuses in which patient_ref may be set (invariant 4.3).
PATIENT_ON_BOARD_STATUSES = {
    AmbulanceStatus.AWAITING_DESTINATION,
    AmbulanceStatus.TRANSPORTING,
    AmbulanceStatus.AT_HOSPITAL,
}


@dataclass
class Ambulance:
    vehicle_id: str
    base_lat: float
    base_lon: float
    lat: float
    lon: float
    speed_kmh: float  # cruising speed from the scenario
    heading: float = 0.0
    status: AmbulanceStatus = AmbulanceStatus.AVAILABLE
    target_lat: float | None = None
    target_lon: float | None = None
    destination_hospital_id: str | None = None
    destination_department: Department | None = None
    placement_id: str | None = None
    patient_ref: str | None = None
    patient_category: str | None = None
    incident_id: str | None = None  # which incident (emergency_call / mass_casualty) it serves
    telemetry_online: bool = True
    last_position_at: datetime | None = None
    current_speed_kmh: float = 0.0  # what VehicleStatus/PositionUpdate report (0 when parked)

    @property
    def is_moving(self) -> bool:
        return self.status in MOVING_STATUSES

    def _transition(self, new_status: AmbulanceStatus) -> None:
        """TODO: raise InvalidTransition if new_status not in ALLOWED_TRANSITIONS[self.status]."""
        raise NotImplementedError

    def dispatch_to_scene(
        self, incident_id: str, lat: float, lon: float, patient_category: str
    ) -> None:
        """AVAILABLE/RETURNING → EN_ROUTE_TO_SCENE. TODO: set target, incident, category."""
        raise NotImplementedError

    def arrive_at_scene(self) -> None:
        """EN_ROUTE_TO_SCENE → AT_SCENE. TODO: clear target, speed 0."""
        raise NotImplementedError

    def load_patient(self, patient_ref: str) -> None:
        """AT_SCENE → AWAITING_DESTINATION. TODO: set patient_ref."""
        raise NotImplementedError

    def assign_destination(
        self, hospital: Hospital, department: Department, placement_id: str | None
    ) -> None:
        """AWAITING_DESTINATION → TRANSPORTING (or TRANSPORTING → TRANSPORTING for REROUTE/REDIRECT).

        TODO: set destination_hospital_id, destination_department, placement_id and the target
        to the hospital's coordinates.
        """
        raise NotImplementedError

    def arrive_at_hospital(self) -> None:
        """TRANSPORTING → AT_HOSPITAL. TODO: clear target, speed 0. Keep patient_ref for the handover."""
        raise NotImplementedError

    def hand_over_and_return(self) -> str:
        """AT_HOSPITAL → RETURNING. Returns the patient_ref handed over.

        TODO: clear patient/destination/placement/incident fields; target = base.
        """
        raise NotImplementedError

    def arrive_at_base(self) -> None:
        """RETURNING → AVAILABLE. TODO: clear target, speed 0."""
        raise NotImplementedError

    def to_vehicle_status(self, updated_at: datetime) -> VehicleStatus:
        """Tracking API view (CLAUDE.md 5.2). `online` = telemetry_online. TODO."""
        raise NotImplementedError

    def to_state(self) -> AmbulanceState:
        """Full state for /sim/state. TODO."""
        raise NotImplementedError


# --------------------------------------------------------------------------- incidents


@dataclass
class Incident:
    """A scene with patients waiting for an ambulance (emergency_call: 1, mass_casualty: N)."""

    incident_id: str
    lat: float
    lon: float
    waiting_categories: list[str]  # one entry per patient still at the scene
    assigned_vehicle_ids: list[str] = field(default_factory=list)

    @property
    def unassigned_patients(self) -> int:
        return len(self.waiting_categories) - len(self.assigned_vehicle_ids)


# --------------------------------------------------------------------------- world


@dataclass
class World:
    hospitals: dict[str, Hospital]
    ambulances: dict[str, Ambulance]
    incidents: dict[str, Incident] = field(default_factory=dict)

    @classmethod
    def from_scenario(
        cls, scenario: Scenario, rng: Random, start_time: datetime, next_patient_ref: PatientRefFn
    ) -> World:
        """Build the initial world from a scenario.

        TODO:
          - build each Hospital via build_hospital
          - build each Ambulance via build_ambulance (parked at base, AVAILABLE)
          - initial occupancy: for each ward, occupy round(beds * initialOccupancy) beds chosen
            with rng.sample, giving each a patient_ref from next_patient_ref()
        NOTE: the engine must also schedule discharges for these initial patients; return the
        world and let the engine walk occupied beds afterwards (keeps World RNG-light).
        """
        raise NotImplementedError

    def hospital(self, hospital_id: str) -> Hospital:
        """TODO: lookup or KeyError."""
        raise NotImplementedError

    def ambulance(self, vehicle_id: str) -> Ambulance:
        """TODO: lookup or KeyError."""
        raise NotImplementedError

    def check_invariants(self) -> list[str]:
        """Return a list of human-readable violations (empty list = all good). CLAUDE.md 4.3.

        TODO:
          - per ward: occupied ≤ total
          - per bed: patient_ref is not None  ⇔  status == OCCUPIED
          - per ambulance: patient_ref is not None ⇒ status in PATIENT_ON_BOARD_STATUSES
          - (bonus) a patient_ref appears in at most one bed across all hospitals
        """
        raise NotImplementedError


def build_hospital(spec: HospitalSpec) -> Hospital:
    """TODO: one Ward per WardSpec, beds named f"{ward.id}-{n:02d}" starting at 01, all FREE."""
    raise NotImplementedError


def build_ambulance(spec: AmbulanceSpec, default_speed_kmh: float) -> Ambulance:
    """TODO: parked at (base_lat, base_lon), speed from spec or default."""
    raise NotImplementedError
