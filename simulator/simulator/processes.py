"""Background processes and random draws (CLAUDE.md Sections 4.4 and 4.5).

Two layers:
  1. Pure draw functions: take the engine's `Random` and return a number. Easy to unit-test.
  2. Handlers: take the engine, mutate the world, emit events, schedule follow-ups.

Every function that needs randomness takes `rng: Random` explicitly. Never `import random` and
call the module-level functions (determinism, CLAUDE.md 4.1).
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

from simulator.contracts import AdtEvent, Department

if TYPE_CHECKING:
    from simulator.engine import Engine
    from simulator.world import Incident

SCENE_MIN_SECONDS = 5 * 60
SCENE_MAX_SECONDS = 15 * 60
CREW_RESPONSE_MIN_SECONDS = 5
CREW_RESPONSE_MAX_SECONDS = 20
HANDOVER_SECONDS = 10 * 60
ARRIVAL_ADMISSION_DELAY_SECONDS = 60  # "after a short delay" (4.6 step 4)
LOS_SIGMA = 0.8  # lognormal shape parameter; spread of length of stay


# --------------------------------------------------------------------------- pure draws


def next_arrival_seconds(rng: Random, rate_per_hour: float) -> float:
    """Inter-arrival time of a Poisson process: exponential with mean 3600 / rate seconds.

    TODO: rng.expovariate(rate_per_hour / 3600). Return float('inf') if rate <= 0.
    """
    raise NotImplementedError


def lognormal_mu(mean: float, sigma: float) -> float:
    """μ such that a lognormal(μ, σ) has the given mean: μ = ln(mean) − σ²/2.  TODO."""
    raise NotImplementedError


def draw_length_of_stay_seconds(rng: Random, mean_hours: float, sigma: float = LOS_SIGMA) -> float:
    """TODO: rng.lognormvariate(lognormal_mu(mean_hours, sigma), sigma) hours → seconds."""
    raise NotImplementedError


def draw_scene_seconds(rng: Random) -> int:
    """TODO: uniform integer in [SCENE_MIN_SECONDS, SCENE_MAX_SECONDS]."""
    raise NotImplementedError


def draw_crew_response_seconds(rng: Random) -> int:
    """TODO: uniform integer in [CREW_RESPONSE_MIN_SECONDS, CREW_RESPONSE_MAX_SECONDS]."""
    raise NotImplementedError


def draw_category(rng: Random, weights: dict[str, float]) -> str:
    """Pick a patient category from mass_casualty `categories` weights.

    TODO: rng.choices(list(keys), weights=list(values))[0]. Iterate in a stable order
    (sorted keys) so the result doesn't depend on YAML ordering quirks.
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- HIS handlers


def schedule_background_admissions(engine: Engine) -> None:
    """Called once after a scenario loads. For every hospital × department with a rate > 0,
    schedule the first arrival via `schedule_next_admission`.

    TODO: iterate hospitals and scenario.background.admissions_per_hour in a stable order.
    """
    raise NotImplementedError


def schedule_next_admission(engine: Engine, hospital_id: str, department: Department) -> None:
    """Schedule the next Poisson arrival for (hospital, department).

    TODO:
      - delay = next_arrival_seconds(engine.rng, rate)
      - engine.schedule_in(delay, <callback that calls background_admission then reschedules>)
      - skip if the hospital has no ward of that department
    """
    raise NotImplementedError


def background_admission(engine: Engine, hospital_id: str, department: Department) -> None:
    """One background arrival (4.4). TODO:
      - free = hospital.free_beds_in(department)
      - if none: engine.count("capacity_full"); return
      - pick one with engine.rng.choice(free)
      - admit_patient(...) with a new patient ref, placement_id=None
    """
    raise NotImplementedError


def admit_patient(
    engine: Engine,
    hospital_id: str,
    ward_id: str,
    bed_id: str,
    patient_ref: str,
    placement_id: str | None,
) -> AdtEvent:
    """Occupy the bed, emit A01, schedule the discharge (and maybe an ED→ICU transfer).

    TODO:
      - bed.occupy(patient_ref, engine.sim_time)
      - build AdtEvent(eventType=A01, ...) and engine.emit_adt(event)
        (emit_adt drops it if the HIS feed is offline: the bed still fills, the event is lost)
      - LOS = draw_length_of_stay_seconds(engine.rng, mean for the ward's department)
      - engine.schedule_in(LOS, discharge_patient(...))
      - if ED and rng.random() < ed_to_icu_transfer_probability: schedule transfer_patient instead
    """
    raise NotImplementedError


def discharge_patient(engine: Engine, hospital_id: str, patient_ref: str) -> None:
    """Free the patient's bed and emit A03.

    TODO: find the patient (they may have been transferred meanwhile: look them up, don't
    trust a stored bed id). If not found, do nothing.
    """
    raise NotImplementedError


def transfer_patient(
    engine: Engine, hospital_id: str, patient_ref: str, to_department: Department
) -> None:
    """Internal transfer (A02), e.g. ED → ICU. Off by default.

    TODO: if a FREE bed exists in to_department, release the old bed, occupy the new one,
    emit A02 with fromWardId/fromBedId, and reschedule discharge from the new ward's LOS.
    If no bed, count "transfer_no_free_bed" and leave the patient where they are.
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- ambulance handlers


def on_arrive_at_scene(engine: Engine, vehicle_id: str) -> None:
    """EN_ROUTE_TO_SCENE reached target. TODO: ambulance.arrive_at_scene(); schedule
    load_patient_at_scene after draw_scene_seconds."""
    raise NotImplementedError


def load_patient_at_scene(engine: Engine, vehicle_id: str) -> None:
    """Scene time over. TODO: mint patient ref, ambulance.load_patient(ref) → AWAITING_DESTINATION;
    remove one waiting patient from the incident (drop the incident when empty)."""
    raise NotImplementedError


def on_arrive_at_hospital(engine: Engine, vehicle_id: str) -> None:
    """TRANSPORTING reached target (4.6 step 4). TODO:
      - ambulance.arrive_at_hospital()
      - schedule arrival_admission after ARRIVAL_ADMISSION_DELAY_SECONDS
      - schedule handover_complete after HANDOVER_SECONDS
    """
    raise NotImplementedError


def arrival_admission(engine: Engine, vehicle_id: str) -> None:
    """Hospital staff admit the ambulance patient (4.6 step 4).

    TODO:
      - free = hospital.free_beds_in(ambulance.destination_department)
      - none → log warning "arrival_no_free_bed", engine.count("arrival_no_free_bed"), admit nothing
      - else admit_patient(..., placement_id=ambulance.placement_id)
    """
    raise NotImplementedError


def handover_complete(engine: Engine, vehicle_id: str) -> None:
    """AT_HOSPITAL over. TODO: ambulance.hand_over_and_return() → RETURNING to base."""
    raise NotImplementedError


def on_arrive_at_base(engine: Engine, vehicle_id: str) -> None:
    """RETURNING reached base. TODO: ambulance.arrive_at_base(); engine.dispatch_waiting_incidents()."""
    raise NotImplementedError


def dispatch_to_incident(engine: Engine, incident: Incident) -> int:
    """Send AVAILABLE ambulances (nearest first, by haversine) to an incident until every
    waiting patient has one or no ambulance is free. Returns how many were dispatched.

    TODO: tie-break equal distances by vehicle_id so it stays deterministic.
    """
    raise NotImplementedError
