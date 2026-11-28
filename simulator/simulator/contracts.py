"""API and event contracts (CLAUDE.md Section 5).

SINGLE SOURCE OF TRUTH. Teammates' code depends on these shapes.
Do not rename a field or change a type without telling the team.

Python attributes are snake_case; the JSON wire format is camelCase (via alias_generator).
Construct with either name; always serialise with `model_dump(mode="json", by_alias=True)`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Contract(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )


# --------------------------------------------------------------------------- enums


class Department(StrEnum):
    ED = "ED"
    ICU = "ICU"
    GENERAL = "GENERAL"
    THEATRE_RECOVERY = "THEATRE_RECOVERY"


class BedStatus(StrEnum):
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class AmbulanceStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    EN_ROUTE_TO_SCENE = "EN_ROUTE_TO_SCENE"
    AT_SCENE = "AT_SCENE"
    AWAITING_DESTINATION = "AWAITING_DESTINATION"
    TRANSPORTING = "TRANSPORTING"
    AT_HOSPITAL = "AT_HOSPITAL"
    RETURNING = "RETURNING"


class AdtEventType(StrEnum):
    A01 = "A01"  # admit
    A02 = "A02"  # transfer
    A03 = "A03"  # discharge


class CrewMessageType(StrEnum):
    DESTINATION = "DESTINATION"
    REROUTE = "REROUTE"
    REDIRECT = "REDIRECT"


class ReceiptStatus(StrEnum):
    DELIVERED = "DELIVERED"
    QUEUED = "QUEUED"


class CrewResponseType(StrEnum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"


class SimStatus(StrEnum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


class InjectionType(StrEnum):
    EMERGENCY_CALL = "emergency_call"
    MASS_CASUALTY = "mass_casualty"
    HIS_FEED_DOWN = "his_feed_down"
    TELEMETRY_OFFLINE = "telemetry_offline"
    ROAD_CONDITION = "road_condition"
    CREW_REJECT_NEXT = "crew_reject_next"
    BEDS_OUT_OF_SERVICE = "beds_out_of_service"


TRAVEL_SOURCE = "SIMULATED_ESTIMATE"


# --------------------------------------------------------------------------- 5.1 HIS


class BedSummary(Contract):
    """A bed as seen through the census. Never carries patientRef."""

    bed_id: str
    status: BedStatus


class WardCensus(Contract):
    ward_id: str
    department: Department
    total_beds: int = Field(ge=0)
    occupied_beds: int = Field(ge=0)
    out_of_service_beds: int = Field(ge=0)
    beds: list[BedSummary]


class BedCensus(Contract):
    hospital_id: str
    as_of: AwareDatetime
    wards: list[WardCensus]


class AdtEvent(Contract):
    event_id: str
    event_type: AdtEventType
    hospital_id: str
    ward_id: str
    bed_id: str
    department: Department
    from_ward_id: str | None = None
    from_bed_id: str | None = None
    patient_ref: str
    placement_id: str | None = None
    occurred_at: AwareDatetime


# --------------------------------------------------------------------------- 5.2 Tracking


class VehicleStatus(Contract):
    vehicle_id: str
    lat: float
    lon: float
    speed_kmh: float
    heading: float
    status: AmbulanceStatus
    destination_hospital_id: str | None = None
    placement_id: str | None = None
    patient_category: str | None = None
    online: bool
    updated_at: AwareDatetime


class CrewMessage(Contract):
    message_id: str
    type: CrewMessageType
    hospital_id: str
    placement_id: str | None = None
    department: Department
    note: str | None = None


class MessageReceipt(Contract):
    message_id: str
    vehicle_id: str
    status: ReceiptStatus


class CrewResponse(Contract):
    message_id: str
    vehicle_id: str
    response: CrewResponseType
    reason: str | None = None
    responded_at: AwareDatetime


class PositionUpdate(Contract):
    """Kafka `ambulance.events`, eventType=PositionUpdate. Partition key: vehicleId."""

    event_type: Literal["PositionUpdate"] = "PositionUpdate"
    event_id: str
    vehicle_id: str
    lat: float
    lon: float
    speed_kmh: float
    heading: float
    status: AmbulanceStatus
    destination_hospital_id: str | None = None
    placement_id: str | None = None
    timestamp: AwareDatetime


class CrewResponseEvent(CrewResponse):
    """Kafka `ambulance.events`, eventType=CrewResponse. Partition key: vehicleId."""

    event_type: Literal["CrewResponse"] = "CrewResponse"
    event_id: str


AmbulanceEvent = PositionUpdate | CrewResponseEvent


# --------------------------------------------------------------------------- 5.3 Travel


class LatLon(Contract):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class TravelDestination(LatLon):
    id: str


class TravelTimesRequest(Contract):
    origin: LatLon
    destinations: list[TravelDestination]
    vehicle_type: str = "AMBULANCE"


class TravelTime(Contract):
    destination_id: str
    distance_km: float
    duration_seconds: int
    source: str = TRAVEL_SOURCE


class RouteRequest(Contract):
    origin: LatLon
    destination: LatLon
    vehicle_type: str = "AMBULANCE"


class Route(Contract):
    distance_km: float
    duration_seconds: int
    path: list[tuple[float, float]]
    source: str = TRAVEL_SOURCE


class RoadCondition(Contract):
    area_id: str
    condition_id: str
    type: str = "CONGESTION"
    factor: float = Field(gt=0)
    until: AwareDatetime


# --------------------------------------------------------------------------- 5.4 Control


class SpeedRequest(Contract):
    multiplier: float = Field(gt=0)


class InjectRequest(Contract):
    type: InjectionType
    params: dict[str, Any] = Field(default_factory=dict)


class ControlAck(Contract):
    status: SimStatus
    sim_time: AwareDatetime | None
    speed: float


class BedState(Contract):
    """Full bed state for /sim/state (includes patientRef, unlike the census)."""

    bed_id: str
    status: BedStatus
    patient_ref: str | None = None
    occupied_since: AwareDatetime | None = None


class WardState(Contract):
    ward_id: str
    department: Department
    beds: list[BedState]


class HospitalState(Contract):
    hospital_id: str
    name: str
    lat: float
    lon: float
    his_feed_online: bool
    wards: list[WardState]


class AmbulanceState(Contract):
    vehicle_id: str
    base_lat: float
    base_lon: float
    lat: float
    lon: float
    speed_kmh: float
    heading: float
    status: AmbulanceStatus
    target_lat: float | None = None
    target_lon: float | None = None
    destination_hospital_id: str | None = None
    destination_department: Department | None = None
    placement_id: str | None = None
    patient_ref: str | None = None
    patient_category: str | None = None
    telemetry_online: bool
    last_position_at: AwareDatetime | None = None


class SimState(Contract):
    scenario: str | None
    status: SimStatus
    sim_time: AwareDatetime | None
    wall_time: datetime
    speed: float
    tick: int
    counters: dict[str, int]
    hospitals: list[HospitalState]
    ambulances: list[AmbulanceState]
