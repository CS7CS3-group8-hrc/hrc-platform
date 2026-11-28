"""Simulator control (for the team and demos, not the platform). CLAUDE.md 5.4."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Response

from simulator.contracts import ControlAck, InjectRequest, SimState, SpeedRequest
from simulator.routes.deps import EngineDep

router = APIRouter(prefix="/sim", tags=["Simulator control"])


@router.post("/scenario/load", response_model=ControlAck)
def load_scenario(engine: EngineDep, body: Annotated[dict[str, Any], Body()]) -> ControlAck:
    """Body is either {"name": "baseline"} or a full scenario document.

    TODO:
      - if set(body) == {"name"}: scenario = load_scenario(body["name"], engine.settings.scenario_dir)
      - else: scenario = parse_scenario(body)
      - engine.load_scenario(scenario); return _ack(engine)
      - FileNotFoundError → 404, pydantic ValidationError → 422
    """
    raise NotImplementedError


@router.post("/start", response_model=ControlAck)
def start(engine: EngineDep) -> ControlAck:
    """TODO: engine.start(); return _ack(engine)"""
    raise NotImplementedError


@router.post("/pause", response_model=ControlAck)
def pause(engine: EngineDep) -> ControlAck:
    """TODO"""
    raise NotImplementedError


@router.post("/reset", response_model=ControlAck)
def reset(engine: EngineDep) -> ControlAck:
    """TODO"""
    raise NotImplementedError


@router.post("/speed", response_model=ControlAck)
def set_speed(request: SpeedRequest, engine: EngineDep) -> ControlAck:
    """TODO"""
    raise NotImplementedError


@router.post("/inject", response_model=ControlAck)
def inject(request: InjectRequest, engine: EngineDep) -> ControlAck:
    """TODO: engine.inject(request.type, request.params); bad params → 422."""
    raise NotImplementedError


@router.get("/state", response_model=SimState)
def get_state(engine: EngineDep) -> SimState:
    """TODO: engine.snapshot(datetime.now(UTC))  (wall clock is fine here, in the route)."""
    raise NotImplementedError


def _ack(engine: EngineDep) -> ControlAck:
    """TODO: ControlAck(status=engine.status, sim_time=engine._sim_time, speed=engine.speed)."""
    raise NotImplementedError


metrics_router = APIRouter(tags=["Ops"])


@metrics_router.get("/metrics")
def metrics(engine: EngineDep) -> Response:
    """Prometheus text format (milestone 9).

    TODO: simplest approach that keeps state in the engine: build a fresh
    prometheus_client.CollectorRegistry per request, add a Counter/Gauge per entry in
    engine.counters (plus ticks, tick lag, sim status), and return
    Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST).
    """
    raise NotImplementedError
