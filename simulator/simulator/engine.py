"""Simulation engine: clock, tick loop, event queue, seeded RNG, injections (CLAUDE.md 4 and 6).

Design rules:
  - Synchronous core. `step()` advances exactly one sim second. Tests call it directly.
  - `run_forever()` is the only async part: it paces `step()` against the wall clock.
  - FastAPI routes and the run loop share one asyncio event loop, so no locks are needed as
    long as nothing awaits in the middle of a step.
  - All randomness: `self.rng`. All "now": `self.sim_time`. Never wall-clock in sim logic.
  - The engine owns all mutable state. No module-level globals.
"""

from __future__ import annotations

import heapq  # noqa: F401  (needed by schedule_at / _process_due_events)
import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from random import Random
from typing import Any

from simulator.config import Settings
from simulator.contracts import (
    AdtEvent,
    BedCensus,
    CrewMessage,
    CrewResponse,
    InjectionType,
    MessageReceipt,
    RoadCondition,
    Route,
    RouteRequest,
    SimState,
    SimStatus,
    TravelTime,
    TravelTimesRequest,
    VehicleStatus,
)
from simulator.scenario import Scenario
from simulator.sinks import EventSink
from simulator.world import World

log = logging.getLogger(__name__)

TICK_SECONDS = 1


class HisUnavailable(Exception):
    """The hospital's HIS feed is down (route maps this to HTTP 503)."""


class UnknownEntity(KeyError):
    """Unknown hospital / vehicle / message id (route maps this to HTTP 404)."""


class EngineNotLoaded(RuntimeError):
    """No scenario loaded yet."""


@dataclass(order=True)
class ScheduledEvent:
    """An entry in the heapq. Ordered by (at, seq); `seq` breaks ties in insertion order,
    which keeps processing deterministic for events at the same sim time."""

    at: datetime
    seq: int
    label: str = field(compare=False)
    action: Callable[[], None] = field(compare=False)
    cancelled: bool = field(default=False, compare=False)


@dataclass
class PendingCrewMessage:
    vehicle_id: str
    message: CrewMessage
    correlation_id: str | None = None


class Engine:
    def __init__(self, settings: Settings, ambulance_sink: EventSink, adt_sink: EventSink) -> None:
        self.settings = settings
        self.ambulance_sink = ambulance_sink
        self.adt_sink = adt_sink

        self.status: SimStatus = SimStatus.STOPPED
        self.speed: float = settings.sim_speed

        # Set by load_scenario / reset
        self.scenario: Scenario | None = None
        self.rng: Random = Random(0)
        self._sim_time: datetime | None = None
        self.tick_count: int = 0
        self.world: World | None = None

        self._queue: list[ScheduledEvent] = []
        self._seq: int = 0
        self._patient_seq: int = 0

        self.counters: Counter[str] = Counter()

        # Crew messaging (4.6)
        self.crew_responses: dict[str, CrewResponse] = {}  # messageId → response
        self.queued_messages: dict[str, list[PendingCrewMessage]] = {}  # vehicleId → queue
        self.reject_next: dict[str, str] = {}  # vehicleId → reason (crew_reject_next)

        # Road conditions (road_condition injection)
        self.road_conditions: dict[str, RoadCondition] = {}  # conditionId → condition

    # ------------------------------------------------------------------ accessors

    @property
    def sim_time(self) -> datetime:
        if self._sim_time is None:
            raise EngineNotLoaded("no scenario loaded")
        return self._sim_time

    def require_world(self) -> World:
        if self.world is None:
            raise EngineNotLoaded("no scenario loaded")
        return self.world

    def count(self, name: str, n: int = 1) -> None:
        self.counters[name] += n

    # ------------------------------------------------------------------ lifecycle (milestone 2)

    def load_scenario(self, scenario: Scenario) -> None:
        """Load a scenario and reset to STOPPED at its startTime.

        TODO:
          - self.scenario = scenario; then self.reset()
        """
        raise NotImplementedError

    def reset(self) -> None:
        """Rebuild the world from self.scenario as if freshly loaded.

        TODO:
          - status STOPPED, tick 0, clear queue/seq/counters/crew state/road conditions
          - self.rng = Random(scenario.seed); self._sim_time = scenario.start_time
          - self.world = World.from_scenario(...)
          - schedule discharges for initially-occupied beds (processes.discharge_patient)
          - processes.schedule_background_admissions(self)
          - schedule each scenario injection at start_time + parse_offset(inj.at)
        Order matters for determinism: do these in the same order every time.
        """
        raise NotImplementedError

    def start(self) -> None:
        """TODO: STOPPED/PAUSED → RUNNING (EngineNotLoaded if no scenario)."""
        raise NotImplementedError

    def pause(self) -> None:
        """TODO: RUNNING → PAUSED."""
        raise NotImplementedError

    def set_speed(self, multiplier: float) -> None:
        """TODO: validate > 0, store."""
        raise NotImplementedError

    # ------------------------------------------------------------------ scheduling

    def schedule_at(self, at: datetime, label: str, action: Callable[[], None]) -> ScheduledEvent:
        """Push an action onto the heap. TODO: increment self._seq; heapq.heappush; return it."""
        raise NotImplementedError

    def schedule_in(self, delay_seconds: float, label: str, action: Callable[[], None]) -> ScheduledEvent:
        """TODO: schedule_at(sim_time + timedelta(seconds=delay_seconds), ...)."""
        raise NotImplementedError

    def _process_due_events(self) -> None:
        """Pop and run every event with at <= sim_time, in order.

        TODO: while queue and queue[0].at <= sim_time: pop; skip if cancelled; run action.
        Actions may schedule new events at the current time; the loop must pick those up too.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------ tick (milestones 2 and 4)

    def step(self, ticks: int = 1) -> None:
        """Advance the simulation by `ticks` sim seconds. Works in any status (tests call it
        while STOPPED); run_forever only calls it while RUNNING.

        TODO, per tick:
          1. self._sim_time += 1 s; self.tick_count += 1
          2. self._process_due_events()
          3. self._move_ambulances()
          4. if tick_count % settings.position_publish_every_n_ticks == 0: publish positions
          5. self.count("ticks")
        """
        raise NotImplementedError

    def run_for(self, seconds: int) -> None:
        """Convenience for tests. TODO: self.step(seconds)."""
        raise NotImplementedError

    def run_until(self, predicate: Callable[[], bool], max_seconds: int) -> bool:
        """Step one tick at a time until predicate() is True. Returns False on timeout. TODO."""
        raise NotImplementedError

    async def run_forever(self) -> None:
        """Real-time loop, started by the FastAPI lifespan.

        TODO:
          - loop forever: if RUNNING, work out how many sim seconds are owed since the last
            iteration (wall_elapsed × speed, keep the fractional remainder), call step() that
            many times; then await asyncio.sleep(small interval, e.g. 0.05)
          - record tick lag (owed − done) for /metrics
          - catch and log exceptions per iteration so one bad event doesn't kill the loop
        Wall clock is fine HERE (it's pacing, not sim logic).
        """
        raise NotImplementedError

    def _move_ambulances(self) -> None:
        """Advance every moving ambulance by one tick (CLAUDE.md 4.5).

        TODO, for each ambulance in sorted(vehicle_id) with is_moving:
          - effective speed = speed_kmh / congestion_factor()
          - step_km = speed × TICK_SECONDS / 3600
          - update heading (geo.initial_bearing_deg) and position (geo.move_towards)
          - on arrival dispatch by status:
              EN_ROUTE_TO_SCENE → processes.on_arrive_at_scene
              TRANSPORTING      → processes.on_arrive_at_hospital
              RETURNING         → processes.on_arrive_at_base
        """
        raise NotImplementedError

    def _publish_positions(self) -> None:
        """TODO: for each ambulance with telemetry_online, emit a PositionUpdate
        (timestamp = sim_time) and set last_position_at."""
        raise NotImplementedError

    # ------------------------------------------------------------------ ids

    def new_uuid(self) -> str:
        """A UUID from the seeded RNG so event ids are reproducible.

        TODO: str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
        NOTE: this consumes RNG state. That's fine as long as it's called in the same order
        each run, but it means adding a log line that mints an id changes later draws.
        """
        raise NotImplementedError

    def next_patient_ref(self) -> str:
        """TODO: increment self._patient_seq; return f"SIM-PT-{n:06d}"."""
        raise NotImplementedError

    # ------------------------------------------------------------------ emitting

    def emit_adt(self, event: AdtEvent) -> bool:
        """Publish an ADT event unless that hospital's HIS feed is offline (4.3: drop, don't queue).

        TODO: check world.hospital(event.hospital_id).his_feed_online; if offline count
        "adt_dropped_feed_down" and return False; otherwise build an Envelope (key=hospitalId,
        headers=build_headers(...)), adt_sink.publish, count f"adt_{event_type}", return True.
        """
        raise NotImplementedError

    def emit_ambulance_event(self, vehicle_id: str, event: Any, correlation_id: str | None = None) -> None:
        """TODO: Envelope(key=vehicle_id, ...) → ambulance_sink.publish; count by eventType."""
        raise NotImplementedError

    # ------------------------------------------------------------------ HIS API (milestone 3)

    def get_bed_census(self, hospital_id: str) -> BedCensus:
        """TODO: UnknownEntity if missing; HisUnavailable if feed offline; else hospital.to_census(sim_time)."""
        raise NotImplementedError

    # ------------------------------------------------------------------ Tracking API (milestones 4 and 6)

    def get_all_vehicles(self) -> list[VehicleStatus]:
        """TODO: sorted by vehicle_id. updatedAt = last_position_at (stale when telemetry is off!)."""
        raise NotImplementedError

    def get_vehicle(self, vehicle_id: str) -> VehicleStatus:
        """TODO: UnknownEntity if missing."""
        raise NotImplementedError

    def send_crew_message(
        self, vehicle_id: str, message: CrewMessage, correlation_id: str | None = None
    ) -> MessageReceipt:
        """sendCrewMessage (4.6 steps 1 and 5).

        TODO:
          - UnknownEntity for unknown vehicle or unknown message.hospital_id
          - telemetry offline → append to queued_messages[vehicle_id], return QUEUED
          - else self._deliver_crew_message(...), return DELIVERED
        """
        raise NotImplementedError

    def _deliver_crew_message(self, pending: PendingCrewMessage) -> None:
        """Schedule the crew's answer after processes.draw_crew_response_seconds.

        TODO: at answer time call self._answer_crew_message(pending).
        """
        raise NotImplementedError

    def _answer_crew_message(self, pending: PendingCrewMessage) -> None:
        """The crew decides (4.6 steps 2, 3 and 5).

        TODO:
          - REJECTED if vehicle_id in reject_next (pop it, use its reason)
          - REJECTED with a reason if the message doesn't fit the status, e.g. DESTINATION when
            not AWAITING_DESTINATION, or REROUTE/REDIRECT when not TRANSPORTING
          - otherwise ACKNOWLEDGED and ambulance.assign_destination(hospital, department, placement)
          - store CrewResponse in crew_responses; emit CrewResponseEvent on ambulance.events
        """
        raise NotImplementedError

    def get_crew_response(self, message_id: str) -> CrewResponse | None:
        """TODO: None if not answered yet (route maps None → 404)."""
        raise NotImplementedError

    # ------------------------------------------------------------------ Travel API (milestone 5)

    def congestion_factor(self, area_id: str | None = None) -> float:
        """Product (or max, your choice: say which) of active road-condition factors.

        TODO: ignore conditions whose `until` has passed (and prune them). With one region per
        scenario you can ignore area_id or check it against scenario.region.
        """
        raise NotImplementedError

    def travel_times(self, request: TravelTimesRequest) -> list[TravelTime]:
        """TODO: per destination: haversine, then geo.travel_duration_seconds with
        settings.road_distance_factor, speed (ambulance default vs other vehicle type), congestion.
        distance_km reported should be the road-adjusted distance (× road factor)."""
        raise NotImplementedError

    def route(self, request: RouteRequest) -> Route:
        """TODO: as travel_times for one destination, plus path = geo.sample_path(...)."""
        raise NotImplementedError

    def get_road_conditions(self, area_id: str) -> list[RoadCondition]:
        """TODO: active conditions for that area."""
        raise NotImplementedError

    # ------------------------------------------------------------------ injections (milestones 4 and 8)

    def inject(self, type_: InjectionType, params: dict[str, Any]) -> None:
        """Apply an injection now. Dispatch to the _inject_* method for the type.

        TODO: a dict {InjectionType: handler} is tidier than an if/elif chain.
        Validate params (KeyError/ValueError → route maps to 422).
        """
        raise NotImplementedError

    def _inject_emergency_call(self, lat: float, lon: float, patientCategory: str) -> None:
        """TODO: create a 1-patient Incident; processes.dispatch_to_incident. If no ambulance
        is free the incident waits (dispatch_waiting_incidents picks it up later)."""
        raise NotImplementedError

    def _inject_mass_casualty(
        self, lat: float, lon: float, casualties: int, categories: dict[str, float]
    ) -> None:
        """TODO: Incident with `casualties` categories drawn via processes.draw_category."""
        raise NotImplementedError

    def dispatch_waiting_incidents(self) -> None:
        """Called whenever an ambulance becomes AVAILABLE. TODO: oldest incident first."""
        raise NotImplementedError

    def _inject_his_feed_down(self, hospitalId: str, durationMinutes: float) -> None:
        """TODO: his_feed_online = False; schedule restore. Overlapping outages: decide whether
        the later restore wins or extends, and keep it simple."""
        raise NotImplementedError

    def _inject_telemetry_offline(self, vehicleId: str, durationMinutes: float) -> None:
        """TODO: telemetry_online = False; schedule restore, which also delivers queued_messages."""
        raise NotImplementedError

    def _inject_road_condition(self, areaId: str, factor: float, durationMinutes: float) -> None:
        """TODO: add RoadCondition(conditionId=f"RC-{n}", until=sim_time + duration)."""
        raise NotImplementedError

    def _inject_crew_reject_next(self, vehicleId: str, reason: str) -> None:
        """TODO: self.reject_next[vehicleId] = reason."""
        raise NotImplementedError

    def _inject_beds_out_of_service(self, hospitalId: str, department: str, count: int) -> None:
        """TODO: mark up to `count` FREE beds OUT_OF_SERVICE (rng.sample for which ones).
        If fewer are free, mark what's there and count the shortfall."""
        raise NotImplementedError

    # ------------------------------------------------------------------ control view

    def snapshot(self, wall_time: datetime) -> SimState:
        """Everything for GET /sim/state. `wall_time` is passed in by the route, keeping
        wall-clock reads out of the engine. TODO."""
        raise NotImplementedError

