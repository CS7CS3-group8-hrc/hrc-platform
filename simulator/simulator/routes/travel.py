"""Travel-Time Source (EXT-04). CLAUDE.md 5.3."""

from __future__ import annotations

from fastapi import APIRouter

from simulator.contracts import RoadCondition, Route, RouteRequest, TravelTime, TravelTimesRequest
from simulator.routes.deps import EngineDep

router = APIRouter(prefix="/travel", tags=["Travel-Time Source (EXT-04)"])


@router.post("/times", response_model=list[TravelTime])
def get_travel_times(request: TravelTimesRequest, engine: EngineDep) -> list[TravelTime]:
    """getTravelTimes. TODO: return engine.travel_times(request)"""
    raise NotImplementedError


@router.post("/route", response_model=Route)
def get_route(request: RouteRequest, engine: EngineDep) -> Route:
    """getRoute. TODO: return engine.route(request)"""
    raise NotImplementedError


@router.get("/conditions/{area_id}", response_model=list[RoadCondition])
def get_road_conditions(area_id: str, engine: EngineDep) -> list[RoadCondition]:
    """getRoadConditions. TODO: return engine.get_road_conditions(area_id)"""
    raise NotImplementedError
