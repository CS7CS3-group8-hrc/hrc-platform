"""Milestone 1: the JSON examples in CLAUDE.md Section 5 validate and round-trip unchanged."""

from typing import Any

import pytest
from pydantic import BaseModel

from simulator.contracts import (
    AdtEvent,
    BedCensus,
    CrewMessage,
    CrewResponse,
    CrewResponseEvent,
    MessageReceipt,
    PositionUpdate,
    RoadCondition,
    Route,
    TravelTime,
    VehicleStatus,
)

T = "2026-11-20T10:00:05Z"

EXAMPLES: list[tuple[type[BaseModel], dict[str, Any]]] = [
    (
        BedCensus,
        {
            "hospitalId": "H1",
            "asOf": "2026-11-20T10:00:00Z",
            "wards": [
                {
                    "wardId": "H1-ICU",
                    "department": "ICU",
                    "totalBeds": 12,
                    "occupiedBeds": 9,
                    "outOfServiceBeds": 0,
                    "beds": [{"bedId": "H1-ICU-01", "status": "OCCUPIED"}],
                }
            ],
        },
    ),
    (
        AdtEvent,
        {
            "eventId": "e1",
            "eventType": "A01",
            "hospitalId": "H1",
            "wardId": "H1-ICU",
            "bedId": "H1-ICU-03",
            "department": "ICU",
            "fromWardId": None,
            "fromBedId": None,
            "patientRef": "SIM-PT-000123",
            "placementId": None,
            "occurredAt": T,
        },
    ),
    (
        VehicleStatus,
        {
            "vehicleId": "A1",
            "lat": 53.3438,
            "lon": -6.2546,
            "speedKmh": 58.2,
            "heading": 270.0,
            "status": "TRANSPORTING",
            "destinationHospitalId": "H2",
            "placementId": "PL-42",
            "patientCategory": "TRAUMA",
            "online": True,
            "updatedAt": T,
        },
    ),
    (
        CrewMessage,
        {
            "messageId": "m1",
            "type": "DESTINATION",
            "hospitalId": "H2",
            "placementId": "PL-42",
            "department": "ED",
            "note": None,
        },
    ),
    (MessageReceipt, {"messageId": "m1", "vehicleId": "A1", "status": "DELIVERED"}),
    (
        CrewResponse,
        {
            "messageId": "m1",
            "vehicleId": "A1",
            "response": "ACKNOWLEDGED",
            "reason": None,
            "respondedAt": T,
        },
    ),
    (
        CrewResponseEvent,
        {
            "eventType": "CrewResponse",
            "eventId": "e2",
            "messageId": "m1",
            "vehicleId": "A1",
            "response": "REJECTED",
            "reason": "crew busy",
            "respondedAt": T,
        },
    ),
    (
        PositionUpdate,
        {
            "eventType": "PositionUpdate",
            "eventId": "e3",
            "vehicleId": "A1",
            "lat": 53.3438,
            "lon": -6.2546,
            "speedKmh": 58.2,
            "heading": 270.0,
            "status": "TRANSPORTING",
            "destinationHospitalId": "H2",
            "placementId": "PL-42",
            "timestamp": T,
        },
    ),
    (
        TravelTime,
        {"destinationId": "H2", "distanceKm": 4.8, "durationSeconds": 360, "source": "SIMULATED_ESTIMATE"},
    ),
    (
        Route,
        {
            "distanceKm": 4.8,
            "durationSeconds": 360,
            "path": [[53.34, -6.25], [53.35, -6.26]],
            "source": "SIMULATED_ESTIMATE",
        },
    ),
    (
        RoadCondition,
        {"areaId": "dublin", "conditionId": "RC-1", "type": "CONGESTION", "factor": 1.5, "until": T},
    ),
]


@pytest.mark.parametrize(("model", "example"), EXAMPLES, ids=[m.__name__ for m, _ in EXAMPLES])
def test_example_round_trips(model: type[BaseModel], example: dict[str, Any]) -> None:
    parsed = model.model_validate(example)
    assert parsed.model_dump(mode="json", by_alias=True) == example


def test_census_has_no_patient_ref() -> None:
    schema = BedCensus.model_json_schema()
    models = [schema, *schema.get("$defs", {}).values()]
    props = {name for m in models for name in m.get("properties", {})}
    assert "patientRef" not in props
