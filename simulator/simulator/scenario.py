"""Scenario YAML models and loading (CLAUDE.md Section 6).

The Pydantic models are complete. The loading helpers at the bottom are yours to implement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from simulator.contracts import Department, InjectionType


class ScenarioModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class WardSpec(ScenarioModel):
    id: str
    department: Department
    beds: int = Field(gt=0)
    initial_occupancy: float = Field(default=0.0, ge=0.0, le=1.0)


class HospitalSpec(ScenarioModel):
    id: str
    name: str
    lat: float
    lon: float
    wards: list[WardSpec]


class AmbulanceSpec(ScenarioModel):
    id: str
    base_lat: float
    base_lon: float
    speed_kmh: float | None = None  # falls back to defaults.ambulanceSpeedKmh


class DefaultsSpec(ScenarioModel):
    ambulance_speed_kmh: float = Field(default=60.0, gt=0)


class BackgroundSpec(ScenarioModel):
    admissions_per_hour: dict[Department, float] = Field(default_factory=dict)
    mean_length_of_stay_hours: dict[Department, float] = Field(default_factory=dict)
    # Probability that an ED admission is later transferred (A02) to ICU. Off by default.
    ed_to_icu_transfer_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class InjectionSpec(ScenarioModel):
    at: str  # offset from startTime, "+HH:MM:SS"
    type: InjectionType
    params: dict[str, Any] = Field(default_factory=dict)


class Scenario(ScenarioModel):
    name: str
    seed: int
    start_time: AwareDatetime
    region: str
    defaults: DefaultsSpec = Field(default_factory=DefaultsSpec)
    hospitals: list[HospitalSpec]
    background: BackgroundSpec = Field(default_factory=BackgroundSpec)
    ambulances: list[AmbulanceSpec]
    injections: list[InjectionSpec] = Field(default_factory=list)

    # TODO (optional): add a @model_validator(mode="after") that rejects duplicate hospital,
    # ward and ambulance ids, and checks each ward id is unique across the scenario.


# --------------------------------------------------------------------------- loading


def parse_offset(offset: str) -> int:
    """Parse a timeline offset like "+00:10:00" into seconds (600).

    TODO:
      - strip the leading "+", split on ":" into hours, minutes, seconds
      - raise ValueError on anything malformed
    """
    raise NotImplementedError


def scenario_path(name: str, scenario_dir: Path) -> Path:
    """Resolve a scenario name ("baseline") to its YAML file (scenario_dir / "baseline.yaml").

    TODO: raise FileNotFoundError with a helpful message if it doesn't exist.
    Guard against path traversal: `name` comes from an HTTP body, so reject anything that
    isn't a plain file stem (no "/", no "..").
    """
    raise NotImplementedError


def load_scenario(name: str, scenario_dir: Path) -> Scenario:
    """Load and validate a scenario by name.

    TODO: read the YAML with yaml.safe_load, then return parse_scenario(data).
    """
    raise NotImplementedError


def parse_scenario(data: dict[str, Any]) -> Scenario:
    """Validate an already-parsed scenario document (used by POST /sim/scenario/load).

    TODO: Scenario.model_validate(data)
    """
    raise NotImplementedError
