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

import asyncio
import heapq
import logging
import math
import time
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from random import Random
from typing import Any

from simulator import geo, processes
from simulator.config import Settings
from simulator.contracts import (
    AdtEvent,
    AmbulanceStatus,
    BedCensus,
    BedStatus,
    CrewMessage,
    CrewMessageType,
    CrewResponse,
    CrewResponseEvent,
    CrewResponseType,
    Department,
    InjectionType,
    MessageReceipt,
    PositionUpdate,
    ReceiptStatus,
    RoadCondition,
    Route,
    RouteRequest,
    SimState,
    SimStatus,
    TravelTime,
    TravelTimesRequest,
    VehicleStatus,
)
from simulator.scenario import Scenario, parse_offset
from simulator.sinks import Envelope, EventSink, build_headers
from simulator.world import Ambulance, Hospital, Incident, InvalidTransition, World

log = logging.getLogger(__name__)

TICK_SECONDS = 1

# Average speed for non-ambulance vehicle types in travel-time estimates (5.3: only AMBULANCE
# uses the scenario's ambulance speed).
DEFAULT_ROAD_SPEED_KMH = 40.0

# run_forever pacing: how often it wakes, and the most ticks it runs per wake-up so a big
# speed multiplier can't starve the HTTP routes sharing the event loop. Ticks it can't fit
# in are carried over and reported as tick lag.
LOOP_INTERVAL_SECONDS = 0.05
MAX_TICKS_PER_ITERATION = 2000


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
        self._incident_seq: int = 0
        self._condition_seq: int = 0

        self.counters: Counter[str] = Counter()
        self.tick_lag: float = 0.0  # sim seconds owed but not yet run (for /metrics)

        # Crew messaging (4.6)
        self.crew_responses: dict[str, CrewResponse] = {}  # messageId → response
        self.queued_messages: dict[str, list[PendingCrewMessage]] = {}  # vehicleId → queue
        self.reject_next: dict[str, str] = {}  # vehicleId → reason (crew_reject_next)

        # Road conditions (road_condition injection)
        self.road_conditions: dict[str, RoadCondition] = {}  # conditionId → condition

        # Pending "restore" events for outages, so an overlapping outage can extend them.
        self._his_restores: dict[str, ScheduledEvent] = {}  # hospitalId → restore
        self._telemetry_restores: dict[str, ScheduledEvent] = {}  # vehicleId → restore

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

    def require_scenario(self) -> Scenario:
        if self.scenario is None:
            raise EngineNotLoaded("no scenario loaded")
        return self.scenario

    def count(self, name: str, n: int = 1) -> None:
        self.counters[name] += n

    def _hospital(self, hospital_id: str) -> Hospital:
        try:
            return self.require_world().hospital(hospital_id)
        except KeyError:
            raise UnknownEntity(f"unknown hospital {hospital_id!r}") from None

    def _ambulance(self, vehicle_id: str) -> Ambulance:
        try:
            return self.require_world().ambulance(vehicle_id)
        except KeyError:
            raise UnknownEntity(f"unknown vehicle {vehicle_id!r}") from None

    # ------------------------------------------------------------------ lifecycle (milestone 2)

    def load_scenario(self, scenario: Scenario) -> None:
        """Load a scenario and reset to STOPPED at its startTime."""
        self.scenario = scenario
        self.reset()

    def reset(self) -> None:
        """Rebuild the world from self.scenario as if freshly loaded.

        The speed multiplier is a runtime setting and survives a reset.
        Order matters for determinism: the steps below always run in the same order.
        """
        scenario = self.require_scenario()

        self.status = SimStatus.STOPPED
        self.tick_count = 0
        self.tick_lag = 0.0
        self._queue = []
        self._seq = 0
        self._patient_seq = 0
        self._incident_seq = 0
        self._condition_seq = 0
        self.counters = Counter()
        self.crew_responses = {}
        self.queued_messages = {}
        self.reject_next = {}
        self.road_conditions = {}
        self._his_restores = {}
        self._telemetry_restores = {}

        self.rng = Random(scenario.seed)
        self._sim_time = scenario.start_time
        self.world = World.from_scenario(
            scenario, self.rng, scenario.start_time, self.next_patient_ref
        )
        for amb in self.world.ambulances.values():
            amb.last_position_at = scenario.start_time

        self._schedule_initial_discharges()
        processes.schedule_background_admissions(self)
        for spec in scenario.injections:
            at = scenario.start_time + timedelta(seconds=parse_offset(spec.at))
            self.schedule_at(
                at,
                f"injection:{spec.type}",
                partial(self.inject, spec.type, dict(spec.params)),
            )

    def _schedule_initial_discharges(self) -> None:
        """Give every patient already in a bed at start-up a discharge time.

        Each gets a full length-of-stay draw from now. A department with no mean LOS in the
        scenario has no discharges scheduled (those patients stay put).
        """
        scenario = self.require_scenario()
        mean_los = scenario.background.mean_length_of_stay_hours
        for hospital in self.require_world().hospitals.values():
            for ward in hospital.wards:
                if ward.department not in mean_los:
                    continue
                for bed in ward.beds_with_status(BedStatus.OCCUPIED):
                    assert bed.patient_ref is not None
                    los = processes.draw_length_of_stay_seconds(self.rng, mean_los[ward.department])
                    self.schedule_in(
                        los,
                        f"discharge:{bed.patient_ref}",
                        partial(
                            processes.discharge_patient, self, hospital.hospital_id, bed.patient_ref
                        ),
                    )

    def start(self) -> None:
        """STOPPED/PAUSED → RUNNING. Starting while RUNNING is a no-op."""
        self.require_world()
        self.status = SimStatus.RUNNING

    def pause(self) -> None:
        """RUNNING → PAUSED. Pausing while PAUSED is a no-op; while STOPPED it's an error."""
        self.require_world()
        if self.status is SimStatus.STOPPED:
            raise InvalidTransition("cannot pause: simulation is STOPPED")
        self.status = SimStatus.PAUSED

    def set_speed(self, multiplier: float) -> None:
        """Store a new speed multiplier (must be a finite number > 0)."""
        if not math.isfinite(multiplier) or multiplier <= 0:
            raise ValueError(f"speed multiplier must be > 0, got {multiplier}")
        self.speed = multiplier

    # ------------------------------------------------------------------ scheduling

    def schedule_at(self, at: datetime, label: str, action: Callable[[], None]) -> ScheduledEvent:
        """Push an action onto the heap and return it (set .cancelled = True to cancel)."""
        self._seq += 1
        event = ScheduledEvent(at=at, seq=self._seq, label=label, action=action)
        heapq.heappush(self._queue, event)
        return event

    def schedule_in(
        self, delay_seconds: float, label: str, action: Callable[[], None]
    ) -> ScheduledEvent:
        """Schedule an action `delay_seconds` sim seconds from now."""
        return self.schedule_at(self.sim_time + timedelta(seconds=delay_seconds), label, action)

    def _process_due_events(self) -> None:
        """Pop and run every event with at <= sim_time, in (time, insertion) order.

        Actions may schedule new events at the current time; the loop picks those up too.
        """
        while self._queue and self._queue[0].at <= self.sim_time:
            event = heapq.heappop(self._queue)
            if not event.cancelled:
                event.action()

    # ------------------------------------------------------------------ tick (milestones 2 and 4)

    def step(self, ticks: int = 1) -> None:
        """Advance the simulation by `ticks` sim seconds. Works in any status (tests call it
        while STOPPED); run_forever only calls it while RUNNING."""
        for _ in range(ticks):
            self._sim_time = self.sim_time + timedelta(seconds=TICK_SECONDS)
            self.tick_count += 1
            self._process_due_events()
            self._move_ambulances()
            if self.tick_count % self.settings.position_publish_every_n_ticks == 0:
                self._publish_positions()
            self.count("ticks")

    def run_for(self, seconds: int) -> None:
        """Convenience for tests."""
        self.step(seconds)

    def run_until(self, predicate: Callable[[], bool], max_seconds: int) -> bool:
        """Step one tick at a time until predicate() is True. Returns False on timeout."""
        for _ in range(max_seconds):
            if predicate():
                return True
            self.step()
        return predicate()

    async def run_forever(self) -> None:
        """Real-time loop, started by the FastAPI lifespan. Wall clock is fine HERE: it only
        paces the ticks, it never feeds into sim logic."""
        owed = 0.0  # sim seconds owed, including the fractional remainder
        last = time.monotonic()
        while True:
            now = time.monotonic()
            elapsed, last = now - last, now
            if self.status is SimStatus.RUNNING:
                owed += elapsed * self.speed
                ticks = min(int(owed), MAX_TICKS_PER_ITERATION)
                try:
                    self.step(ticks)
                except Exception:
                    log.exception("tick failed", extra={"simTime": str(self._sim_time)})
                    self.count("loop_errors")
                owed -= ticks
                self.tick_lag = owed
            else:
                owed = 0.0
                self.tick_lag = 0.0
            await asyncio.sleep(LOOP_INTERVAL_SECONDS)

    def _move_ambulances(self) -> None:
        """Advance every moving ambulance by one tick (CLAUDE.md 4.5).

        The moving set is fixed before anyone moves, so an ambulance dispatched by another's
        arrival this tick starts moving next tick, whatever its id.
        """
        world = self.require_world()
        moving = [
            world.ambulances[vid]
            for vid in sorted(world.ambulances)
            if world.ambulances[vid].is_moving
        ]
        if not moving:
            return
        congestion = self.congestion_factor()
        for amb in moving:
            if amb.target_lat is None or amb.target_lon is None:
                continue
            speed = amb.speed_kmh / congestion
            step_km = speed * TICK_SECONDS / 3600
            current, target = (amb.lat, amb.lon), (amb.target_lat, amb.target_lon)
            amb.heading = geo.initial_bearing_deg(*current, *target)
            (amb.lat, amb.lon), arrived = geo.move_towards(current, target, step_km)
            amb.current_speed_kmh = speed
            if not arrived:
                continue
            if amb.status is AmbulanceStatus.EN_ROUTE_TO_SCENE:
                processes.on_arrive_at_scene(self, amb.vehicle_id)
            elif amb.status is AmbulanceStatus.TRANSPORTING:
                processes.on_arrive_at_hospital(self, amb.vehicle_id)
            elif amb.status is AmbulanceStatus.RETURNING:
                processes.on_arrive_at_base(self, amb.vehicle_id)

    def _publish_positions(self) -> None:
        """Emit a PositionUpdate (timestamp = sim_time) for every ambulance with telemetry."""
        world = self.require_world()
        for vid in sorted(world.ambulances):
            amb = world.ambulances[vid]
            if not amb.telemetry_online:
                continue
            self.emit_ambulance_event(
                vid,
                PositionUpdate(
                    event_id=self.new_uuid(),
                    vehicle_id=vid,
                    lat=amb.lat,
                    lon=amb.lon,
                    speed_kmh=amb.current_speed_kmh,
                    heading=amb.heading,
                    status=amb.status,
                    destination_hospital_id=amb.destination_hospital_id,
                    placement_id=amb.placement_id,
                    timestamp=self.sim_time,
                ),
            )
            amb.last_position_at = self.sim_time

    # ------------------------------------------------------------------ ids

    def new_uuid(self) -> str:
        """A UUID from the seeded RNG so event ids are reproducible.

        NOTE: this consumes RNG state. That's fine as long as it's called in the same order
        each run, but it means adding a log line that mints an id changes later draws.
        """
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def next_patient_ref(self) -> str:
        self._patient_seq += 1
        return f"SIM-PT-{self._patient_seq:06d}"

    # ------------------------------------------------------------------ emitting

    def emit_adt(self, event: AdtEvent) -> bool:
        """Publish an ADT event unless that hospital's HIS feed is offline (4.3: drop, don't
        queue). Returns whether it was published."""
        if not self._hospital(event.hospital_id).his_feed_online:
            self.count("adt_dropped_feed_down")
            return False
        self.adt_sink.publish(
            Envelope(
                key=event.hospital_id,
                event=event,
                headers=build_headers(event.event_id, self.sim_time),
            )
        )
        self.count(f"adt_{event.event_type}")
        return True

    def emit_ambulance_event(
        self,
        vehicle_id: str,
        event: PositionUpdate | CrewResponseEvent,
        correlation_id: str | None = None,
    ) -> None:
        """Publish to ambulance.events, partitioned by vehicleId."""
        self.ambulance_sink.publish(
            Envelope(
                key=vehicle_id,
                event=event,
                headers=build_headers(event.event_id, self.sim_time, correlation_id),
            )
        )
        self.count(f"ambulance_{event.event_type}")

    # ------------------------------------------------------------------ HIS API (milestone 3)

    def get_bed_census(self, hospital_id: str) -> BedCensus:
        hospital = self._hospital(hospital_id)
        if not hospital.his_feed_online:
            raise HisUnavailable(f"HIS feed for {hospital_id} is offline")
        return hospital.to_census(self.sim_time)

    # ------------------------------------------------------------------ Tracking API (milestones 4 and 6)

    def get_all_vehicles(self) -> list[VehicleStatus]:
        """Sorted by vehicle_id. updatedAt = last_position_at, so it goes stale while the
        vehicle's telemetry is offline."""
        world = self.require_world()
        return [self.get_vehicle(vid) for vid in sorted(world.ambulances)]

    def get_vehicle(self, vehicle_id: str) -> VehicleStatus:
        amb = self._ambulance(vehicle_id)
        return amb.to_vehicle_status(amb.last_position_at or self.sim_time)

    def send_crew_message(
        self, vehicle_id: str, message: CrewMessage, correlation_id: str | None = None
    ) -> MessageReceipt:
        """sendCrewMessage (4.6 steps 1 and 5). QUEUED while telemetry is offline."""
        amb = self._ambulance(vehicle_id)
        self._hospital(message.hospital_id)
        pending = PendingCrewMessage(vehicle_id, message, correlation_id)
        self.count("crew_messages_received")
        if not amb.telemetry_online:
            self.queued_messages.setdefault(vehicle_id, []).append(pending)
            return MessageReceipt(
                message_id=message.message_id, vehicle_id=vehicle_id, status=ReceiptStatus.QUEUED
            )
        self._deliver_crew_message(pending)
        return MessageReceipt(
            message_id=message.message_id, vehicle_id=vehicle_id, status=ReceiptStatus.DELIVERED
        )

    def _deliver_crew_message(self, pending: PendingCrewMessage) -> None:
        """Schedule the crew's answer after processes.draw_crew_response_seconds."""
        self.schedule_in(
            processes.draw_crew_response_seconds(self.rng),
            f"crew_answer:{pending.message.message_id}",
            lambda: self._answer_crew_message(pending),
        )

    def _answer_crew_message(self, pending: PendingCrewMessage) -> None:
        """The crew decides (4.6 steps 2, 3 and 5)."""
        amb = self._ambulance(pending.vehicle_id)
        message = pending.message
        reason: str | None = None
        if pending.vehicle_id in self.reject_next:
            reason = self.reject_next.pop(pending.vehicle_id)
        elif (
            message.type is CrewMessageType.DESTINATION
            and amb.status is not AmbulanceStatus.AWAITING_DESTINATION
        ):
            reason = f"DESTINATION not accepted while {amb.status}"
        elif (
            message.type in (CrewMessageType.REROUTE, CrewMessageType.REDIRECT)
            and amb.status is not AmbulanceStatus.TRANSPORTING
        ):
            reason = f"{message.type} not accepted while {amb.status}"

        if reason is None:
            amb.assign_destination(
                self._hospital(message.hospital_id), message.department, message.placement_id
            )
            response_type = CrewResponseType.ACKNOWLEDGED
        else:
            response_type = CrewResponseType.REJECTED

        response = CrewResponse(
            message_id=message.message_id,
            vehicle_id=pending.vehicle_id,
            response=response_type,
            reason=reason,
            responded_at=self.sim_time,
        )
        self.crew_responses[message.message_id] = response
        self.emit_ambulance_event(
            pending.vehicle_id,
            CrewResponseEvent(event_id=self.new_uuid(), **response.model_dump()),
            pending.correlation_id,
        )

    def get_crew_response(self, message_id: str) -> CrewResponse | None:
        """None if not answered yet (route maps None → 404)."""
        return self.crew_responses.get(message_id)

    # ------------------------------------------------------------------ Travel API (milestone 5)

    def _active_road_conditions(self) -> list[RoadCondition]:
        """Prune expired conditions and return the rest, oldest first."""
        now = self.sim_time
        for cid in [c for c, rc in self.road_conditions.items() if rc.until <= now]:
            del self.road_conditions[cid]
        return list(self.road_conditions.values())

    def congestion_factor(self, area_id: str | None = None) -> float:
        """The largest active road-condition factor (1.0 when there are none).

        Max, not product: two overlapping congestion reports for the same city shouldn't
        compound. `area_id=None` means every area (a scenario has one region).
        """
        factors = [
            rc.factor
            for rc in self._active_road_conditions()
            if area_id is None or rc.area_id == area_id
        ]
        return max(factors, default=1.0)

    def _vehicle_speed_kmh(self, vehicle_type: str) -> float:
        if vehicle_type.upper() == "AMBULANCE":
            return self.require_scenario().defaults.ambulance_speed_kmh
        return DEFAULT_ROAD_SPEED_KMH

    def _estimate(
        self, origin: tuple[float, float], dest: tuple[float, float], vehicle_type: str
    ) -> tuple[float, int]:
        """(road-adjusted distance km, duration seconds) for one origin/destination pair."""
        straight_km = geo.haversine_km(*origin, *dest)
        factor = self.settings.road_distance_factor
        duration = geo.travel_duration_seconds(
            straight_km, self._vehicle_speed_kmh(vehicle_type), factor, self.congestion_factor()
        )
        return round(straight_km * factor, 3), duration

    def travel_times(self, request: TravelTimesRequest) -> list[TravelTime]:
        origin = (request.origin.lat, request.origin.lon)
        result = []
        for dest in request.destinations:
            distance_km, duration = self._estimate(
                origin, (dest.lat, dest.lon), request.vehicle_type
            )
            result.append(
                TravelTime(
                    destination_id=dest.id, distance_km=distance_km, duration_seconds=duration
                )
            )
        return result

    def route(self, request: RouteRequest) -> Route:
        origin = (request.origin.lat, request.origin.lon)
        dest = (request.destination.lat, request.destination.lon)
        distance_km, duration = self._estimate(origin, dest, request.vehicle_type)
        return Route(
            distance_km=distance_km,
            duration_seconds=duration,
            path=geo.sample_path(origin, dest),
        )

    def get_road_conditions(self, area_id: str) -> list[RoadCondition]:
        """Active conditions for that area (empty for an unknown area)."""
        return [rc for rc in self._active_road_conditions() if rc.area_id == area_id]

    # ------------------------------------------------------------------ injections (milestones 4 and 8)

    def inject(self, type_: InjectionType, params: dict[str, Any]) -> None:
        """Apply an injection now. Missing or unexpected params raise ValueError (→ 422)."""
        self.require_world()
        handlers: dict[InjectionType, Callable[..., None]] = {
            InjectionType.EMERGENCY_CALL: self._inject_emergency_call,
            InjectionType.MASS_CASUALTY: self._inject_mass_casualty,
            InjectionType.HIS_FEED_DOWN: self._inject_his_feed_down,
            InjectionType.TELEMETRY_OFFLINE: self._inject_telemetry_offline,
            InjectionType.ROAD_CONDITION: self._inject_road_condition,
            InjectionType.CREW_REJECT_NEXT: self._inject_crew_reject_next,
            InjectionType.BEDS_OUT_OF_SERVICE: self._inject_beds_out_of_service,
        }
        handler = handlers[InjectionType(type_)]
        try:
            handler(**params)
        except TypeError as exc:
            raise ValueError(f"bad params for {type_}: {exc}") from exc
        self.count(f"injection_{InjectionType(type_).value}")
        log.info("injection applied", extra={"simTime": self.sim_time.isoformat(), "type": type_})

    def _new_incident(self, lat: float, lon: float, categories: list[str]) -> Incident:
        self._incident_seq += 1
        incident = Incident(f"INC-{self._incident_seq}", float(lat), float(lon), categories)
        self.require_world().incidents[incident.incident_id] = incident
        return incident

    def _inject_emergency_call(self, lat: float, lon: float, patientCategory: str) -> None:
        """A 1-patient incident. If no ambulance is free it waits (dispatch_waiting_incidents
        picks it up when one becomes AVAILABLE)."""
        incident = self._new_incident(lat, lon, [patientCategory])
        if processes.dispatch_to_incident(self, incident) == 0:
            self.count("incident_waiting")

    def _inject_mass_casualty(
        self, lat: float, lon: float, casualties: int, categories: dict[str, float]
    ) -> None:
        if int(casualties) <= 0:
            raise ValueError("casualties must be > 0")
        drawn = [processes.draw_category(self.rng, categories) for _ in range(int(casualties))]
        incident = self._new_incident(lat, lon, drawn)
        processes.dispatch_to_incident(self, incident)

    def dispatch_waiting_incidents(self) -> None:
        """Called whenever an ambulance becomes AVAILABLE. Oldest incident first (dicts keep
        insertion order); stops as soon as no ambulance is left to send."""
        for incident in list(self.require_world().incidents.values()):
            if (
                incident.unassigned_patients > 0
                and processes.dispatch_to_incident(self, incident) == 0
            ):
                break

    def _restore_later(
        self,
        restores: dict[str, ScheduledEvent],
        key: str,
        minutes: float,
        label: str,
        action: Callable[[], None],
    ) -> None:
        """Schedule a restore. Overlapping outages EXTEND: the restore that lands latest wins,
        and an earlier pending one is cancelled so it can't end the outage early."""
        at = self.sim_time + timedelta(minutes=float(minutes))
        previous = restores.get(key)
        if previous is not None and not previous.cancelled:
            if previous.at >= at:
                return
            previous.cancelled = True

        def run() -> None:
            restores.pop(key, None)
            action()

        restores[key] = self.schedule_at(at, label, run)

    def _inject_his_feed_down(self, hospitalId: str, durationMinutes: float) -> None:
        hospital = self._hospital(hospitalId)
        hospital.his_feed_online = False

        def restore() -> None:
            hospital.his_feed_online = True
            log.info("HIS feed restored", extra={"hospitalId": hospitalId})

        self._restore_later(
            self._his_restores, hospitalId, durationMinutes, f"his_restore:{hospitalId}", restore
        )

    def _inject_telemetry_offline(self, vehicleId: str, durationMinutes: float) -> None:
        amb = self._ambulance(vehicleId)
        amb.telemetry_online = False

        def restore() -> None:
            amb.telemetry_online = True
            for pending in self.queued_messages.pop(vehicleId, []):
                self._deliver_crew_message(pending)

        self._restore_later(
            self._telemetry_restores,
            vehicleId,
            durationMinutes,
            f"telemetry_restore:{vehicleId}",
            restore,
        )

    def _inject_road_condition(self, areaId: str, factor: float, durationMinutes: float) -> None:
        self._condition_seq += 1
        condition = RoadCondition(
            area_id=areaId,
            condition_id=f"RC-{self._condition_seq}",
            factor=factor,
            until=self.sim_time + timedelta(minutes=float(durationMinutes)),
        )
        self.road_conditions[condition.condition_id] = condition

    def _inject_crew_reject_next(self, vehicleId: str, reason: str) -> None:
        self._ambulance(vehicleId)
        self.reject_next[vehicleId] = reason

    def _inject_beds_out_of_service(self, hospitalId: str, department: str, count: int) -> None:
        """Mark up to `count` FREE beds OUT_OF_SERVICE (rng.sample picks which). If fewer are
        free, mark what's there and count the shortfall."""
        hospital = self._hospital(hospitalId)
        free = [bed for _, bed in hospital.free_beds_in(Department(department))]
        n = min(int(count), len(free))
        for bed in self.rng.sample(free, n):
            bed.mark_out_of_service()
        if n < int(count):
            self.count("beds_out_of_service_shortfall", int(count) - n)

    # ------------------------------------------------------------------ control view

    def snapshot(self, wall_time: datetime) -> SimState:
        """Everything for GET /sim/state. `wall_time` is passed in by the route, keeping
        wall-clock reads out of the engine. Works before a scenario is loaded."""
        world = self.world
        return SimState(
            scenario=self.scenario.name if self.scenario else None,
            status=self.status,
            sim_time=self._sim_time,
            wall_time=wall_time,
            speed=self.speed,
            tick=self.tick_count,
            counters=dict(self.counters),
            hospitals=[h.to_state() for h in world.hospitals.values()] if world else [],
            ambulances=(
                [world.ambulances[v].to_state() for v in sorted(world.ambulances)] if world else []
            ),
        )
