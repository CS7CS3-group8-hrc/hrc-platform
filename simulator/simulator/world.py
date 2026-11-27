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
    BedState,
    BedStatus,
    BedSummary,
    Department,
    HospitalState,
    VehicleStatus,
    WardCensus,
    WardState,
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
        """FREE → OCCUPIED."""
        if self.status is not BedStatus.FREE:
            raise InvalidTransition(f"bed {self.bed_id}: cannot occupy, status is {self.status}")
        self.status = BedStatus.OCCUPIED
        self.patient_ref = patient_ref
        self.occupied_since = at

    def release(self) -> str:
        """OCCUPIED → FREE. Returns the patient_ref that left."""
        if self.status is not BedStatus.OCCUPIED or self.patient_ref is None:
            raise InvalidTransition(f"bed {self.bed_id}: cannot release, status is {self.status}")
        patient_ref = self.patient_ref
        self.status = BedStatus.FREE
        self.patient_ref = None
        self.occupied_since = None
        return patient_ref

    def mark_out_of_service(self) -> None:
        """FREE → OUT_OF_SERVICE."""
        if self.status is not BedStatus.FREE:
            raise InvalidTransition(
                f"bed {self.bed_id}: cannot take out of service, status is {self.status}"
            )
        self.status = BedStatus.OUT_OF_SERVICE


@dataclass
class Ward:
    ward_id: str
    department: Department
    beds: list[Bed]

    @property
    def total_beds(self) -> int:
        return len(self.beds)

    def beds_with_status(self, status: BedStatus) -> list[Bed]:
        """Beds in this ward with the given status, in list order (determinism)."""
        return [bed for bed in self.beds if bed.status is status]

    def find_patient(self, patient_ref: str) -> Bed | None:
        """The bed holding this patient, or None."""
        return next((bed for bed in self.beds if bed.patient_ref == patient_ref), None)


@dataclass
class Hospital:
    hospital_id: str
    name: str
    lat: float
    lon: float
    wards: list[Ward]
    his_feed_online: bool = True

    def wards_in(self, department: Department) -> list[Ward]:
        """All wards of this department (a hospital may have more than one)."""
        return [ward for ward in self.wards if ward.department is department]

    def free_beds_in(self, department: Department) -> list[tuple[Ward, Bed]]:
        """Every FREE bed in that department, paired with its ward, in stable order."""
        return [
            (ward, bed)
            for ward in self.wards_in(department)
            for bed in ward.beds_with_status(BedStatus.FREE)
        ]

    def find_patient(self, patient_ref: str) -> tuple[Ward, Bed] | None:
        """Locate a patient anywhere in this hospital."""
        for ward in self.wards:
            bed = ward.find_patient(patient_ref)
            if bed is not None:
                return ward, bed
        return None

    def to_census(self, as_of: datetime) -> BedCensus:
        """Build the HIS census (CLAUDE.md 5.1). MUST NOT include patientRef."""
        return BedCensus(
            hospital_id=self.hospital_id,
            as_of=as_of,
            wards=[
                WardCensus(
                    ward_id=ward.ward_id,
                    department=ward.department,
                    total_beds=ward.total_beds,
                    occupied_beds=len(ward.beds_with_status(BedStatus.OCCUPIED)),
                    out_of_service_beds=len(ward.beds_with_status(BedStatus.OUT_OF_SERVICE)),
                    beds=[BedSummary(bed_id=b.bed_id, status=b.status) for b in ward.beds],
                )
                for ward in self.wards
            ],
        )

    def to_state(self) -> HospitalState:
        """Full state for /sim/state (includes patientRef)."""
        return HospitalState(
            hospital_id=self.hospital_id,
            name=self.name,
            lat=self.lat,
            lon=self.lon,
            his_feed_online=self.his_feed_online,
            wards=[
                WardState(
                    ward_id=ward.ward_id,
                    department=ward.department,
                    beds=[
                        BedState(
                            bed_id=b.bed_id,
                            status=b.status,
                            patient_ref=b.patient_ref,
                            occupied_since=b.occupied_since,
                        )
                        for b in ward.beds
                    ],
                )
                for ward in self.wards
            ],
        )


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
        """Move to new_status, or raise InvalidTransition if the graph doesn't allow it."""
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransition(
                f"ambulance {self.vehicle_id}: {self.status} -> {new_status} is not allowed"
            )
        self.status = new_status

    def _stop(self) -> None:
        """Clear the movement target and park (speed 0)."""
        self.target_lat = None
        self.target_lon = None
        self.current_speed_kmh = 0.0

    def dispatch_to_scene(
        self, incident_id: str, lat: float, lon: float, patient_category: str
    ) -> None:
        """AVAILABLE/RETURNING → EN_ROUTE_TO_SCENE."""
        self._transition(AmbulanceStatus.EN_ROUTE_TO_SCENE)
        self.target_lat = lat
        self.target_lon = lon
        self.incident_id = incident_id
        self.patient_category = patient_category

    def arrive_at_scene(self) -> None:
        """EN_ROUTE_TO_SCENE → AT_SCENE."""
        self._transition(AmbulanceStatus.AT_SCENE)
        self._stop()

    def load_patient(self, patient_ref: str) -> None:
        """AT_SCENE → AWAITING_DESTINATION."""
        self._transition(AmbulanceStatus.AWAITING_DESTINATION)
        self.patient_ref = patient_ref

    def assign_destination(
        self, hospital: Hospital, department: Department, placement_id: str | None
    ) -> None:
        """AWAITING_DESTINATION → TRANSPORTING (or TRANSPORTING → TRANSPORTING for REROUTE/REDIRECT)."""
        self._transition(AmbulanceStatus.TRANSPORTING)
        self.destination_hospital_id = hospital.hospital_id
        self.destination_department = department
        self.placement_id = placement_id
        self.target_lat = hospital.lat
        self.target_lon = hospital.lon

    def arrive_at_hospital(self) -> None:
        """TRANSPORTING → AT_HOSPITAL. Keeps patient_ref for the handover."""
        self._transition(AmbulanceStatus.AT_HOSPITAL)
        self._stop()

    def hand_over_and_return(self) -> str:
        """AT_HOSPITAL → RETURNING. Returns the patient_ref handed over."""
        if self.patient_ref is None:
            raise InvalidTransition(f"ambulance {self.vehicle_id}: no patient to hand over")
        self._transition(AmbulanceStatus.RETURNING)
        patient_ref = self.patient_ref
        self.patient_ref = None
        self.patient_category = None
        self.destination_hospital_id = None
        self.destination_department = None
        self.placement_id = None
        self.incident_id = None
        self.target_lat = self.base_lat
        self.target_lon = self.base_lon
        return patient_ref

    def arrive_at_base(self) -> None:
        """RETURNING → AVAILABLE."""
        self._transition(AmbulanceStatus.AVAILABLE)
        self._stop()

    def to_vehicle_status(self, updated_at: datetime) -> VehicleStatus:
        """Tracking API view (CLAUDE.md 5.2). `online` = telemetry_online."""
        return VehicleStatus(
            vehicle_id=self.vehicle_id,
            lat=self.lat,
            lon=self.lon,
            speed_kmh=self.current_speed_kmh,
            heading=self.heading,
            status=self.status,
            destination_hospital_id=self.destination_hospital_id,
            placement_id=self.placement_id,
            patient_category=self.patient_category,
            online=self.telemetry_online,
            updated_at=updated_at,
        )

    def to_state(self) -> AmbulanceState:
        """Full state for /sim/state. speedKmh is the current speed, as in VehicleStatus."""
        return AmbulanceState(
            vehicle_id=self.vehicle_id,
            base_lat=self.base_lat,
            base_lon=self.base_lon,
            lat=self.lat,
            lon=self.lon,
            speed_kmh=self.current_speed_kmh,
            heading=self.heading,
            status=self.status,
            target_lat=self.target_lat,
            target_lon=self.target_lon,
            destination_hospital_id=self.destination_hospital_id,
            destination_department=self.destination_department,
            placement_id=self.placement_id,
            patient_ref=self.patient_ref,
            patient_category=self.patient_category,
            telemetry_online=self.telemetry_online,
            last_position_at=self.last_position_at,
        )


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

        Initial occupancy: each ward gets round(beds * initialOccupancy) OCCUPIED beds, chosen
        with rng.sample, each with a fresh patient_ref and occupied_since = start_time.
        Hospitals and wards are walked in scenario order, so the RNG draws are deterministic.

        NOTE: the engine must also schedule discharges for these initial patients; it walks
        the occupied beds after this returns (keeps World RNG-light).
        """
        hospitals: dict[str, Hospital] = {}
        for hospital_spec in scenario.hospitals:
            hospital = build_hospital(hospital_spec)
            for ward, ward_spec in zip(hospital.wards, hospital_spec.wards, strict=True):
                n_occupied = round(ward_spec.beds * ward_spec.initial_occupancy)
                chosen = rng.sample(ward.beds, n_occupied)
                # Occupy in bed order, not sample order, so patient refs run along the ward.
                for bed in sorted(chosen, key=ward.beds.index):
                    bed.occupy(next_patient_ref(), start_time)
            hospitals[hospital.hospital_id] = hospital

        ambulances = {
            spec.id: build_ambulance(spec, scenario.defaults.ambulance_speed_kmh)
            for spec in scenario.ambulances
        }
        return cls(hospitals=hospitals, ambulances=ambulances)

    def hospital(self, hospital_id: str) -> Hospital:
        """Lookup by id, or KeyError."""
        return self.hospitals[hospital_id]

    def ambulance(self, vehicle_id: str) -> Ambulance:
        """Lookup by id, or KeyError."""
        return self.ambulances[vehicle_id]

    def check_invariants(self) -> list[str]:
        """Return a list of human-readable violations (empty list = all good). CLAUDE.md 4.3.

        Checks:
          - per ward: occupied ≤ total
          - per bed: patient_ref is not None  ⇔  status == OCCUPIED
          - per ambulance: patient_ref is not None ⇒ status in PATIENT_ON_BOARD_STATUSES
          - a patient_ref appears in at most one bed across all hospitals
        """
        violations: list[str] = []
        bed_of_patient: dict[str, str] = {}

        for hospital in self.hospitals.values():
            for ward in hospital.wards:
                occupied = len(ward.beds_with_status(BedStatus.OCCUPIED))
                if occupied > ward.total_beds:
                    violations.append(
                        f"ward {ward.ward_id}: {occupied} occupied > {ward.total_beds} total"
                    )
                for bed in ward.beds:
                    has_patient = bed.patient_ref is not None
                    if has_patient != (bed.status is BedStatus.OCCUPIED):
                        violations.append(
                            f"bed {bed.bed_id}: status {bed.status} with patient_ref {bed.patient_ref!r}"
                        )
                    if bed.patient_ref is not None:
                        other = bed_of_patient.setdefault(bed.patient_ref, bed.bed_id)
                        if other != bed.bed_id:
                            violations.append(
                                f"patient {bed.patient_ref} is in both {other} and {bed.bed_id}"
                            )

        for amb in self.ambulances.values():
            if amb.patient_ref is not None and amb.status not in PATIENT_ON_BOARD_STATUSES:
                violations.append(
                    f"ambulance {amb.vehicle_id}: patient {amb.patient_ref} on board while {amb.status}"
                )
        return violations


def build_hospital(spec: HospitalSpec) -> Hospital:
    """One Ward per WardSpec, beds named f"{ward.id}-{n:02d}" starting at 01, all FREE."""
    return Hospital(
        hospital_id=spec.id,
        name=spec.name,
        lat=spec.lat,
        lon=spec.lon,
        wards=[
            Ward(
                ward_id=ws.id,
                department=ws.department,
                beds=[Bed(bed_id=f"{ws.id}-{n:02d}") for n in range(1, ws.beds + 1)],
            )
            for ws in spec.wards
        ],
    )


def build_ambulance(spec: AmbulanceSpec, default_speed_kmh: float) -> Ambulance:
    """Parked at (base_lat, base_lon), AVAILABLE, speed from spec or the scenario default."""
    return Ambulance(
        vehicle_id=spec.id,
        base_lat=spec.base_lat,
        base_lon=spec.base_lon,
        lat=spec.base_lat,
        lon=spec.base_lon,
        speed_kmh=spec.speed_kmh if spec.speed_kmh is not None else default_speed_kmh,
    )
