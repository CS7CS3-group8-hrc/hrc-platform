"""Ambulance Tracking (EXT-02). CLAUDE.md 5.2."""

from __future__ import annotations

from fastapi import APIRouter, Header

from simulator.contracts import CrewMessage, CrewResponse, MessageReceipt, VehicleStatus
from simulator.routes.deps import EngineDep

router = APIRouter(prefix="/tracking", tags=["Ambulance Tracking (EXT-02)"])


@router.get("/vehicles", response_model=list[VehicleStatus])
def get_all_vehicles(engine: EngineDep) -> list[VehicleStatus]:
    """getAllVehicles. TODO: return engine.get_all_vehicles()"""
    raise NotImplementedError


@router.get("/vehicles/{vehicle_id}", response_model=VehicleStatus)
def get_vehicle_status(vehicle_id: str, engine: EngineDep) -> VehicleStatus:
    """getVehicleStatus. 404 if unknown. TODO."""
    raise NotImplementedError


@router.post("/vehicles/{vehicle_id}/messages", response_model=MessageReceipt)
def send_crew_message(
    vehicle_id: str,
    message: CrewMessage,
    engine: EngineDep,
    x_correlation_id: str | None = Header(default=None),
) -> MessageReceipt:
    """sendCrewMessage. Pass the caller's correlation id through so the CrewResponse event
    carries it. TODO: return engine.send_crew_message(vehicle_id, message, x_correlation_id)"""
    raise NotImplementedError


@router.get("/messages/{message_id}/response", response_model=CrewResponse)
def get_crew_response(message_id: str, engine: EngineDep) -> CrewResponse:
    """getCrewResponse. 404 until the crew has answered.

    TODO: resp = engine.get_crew_response(message_id); raise HTTPException(404) if None.
    """
    raise NotImplementedError
