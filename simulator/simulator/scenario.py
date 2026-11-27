"""Scenario YAML models and loading (CLAUDE.md Section 6).

The Pydantic models are complete. The loading helpers at the bottom are yours to implement.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
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

    @model_validator(mode="after")
    def _check_unique_ids(self) -> Scenario:
        """Reject duplicate hospital and ambulance ids, and ward ids repeated anywhere."""
        _require_unique("hospital", [h.id for h in self.hospitals])
        _require_unique("ward", [w.id for h in self.hospitals for w in h.wards])
        _require_unique("ambulance", [a.id for a in self.ambulances])
        for spec in self.injections:
            parse_offset(spec.at)
        return self


def _require_unique(kind: str, ids: list[str]) -> None:
    dupes = sorted(i for i, n in Counter(ids).items() if n > 1)
    if dupes:
        raise ValueError(f"duplicate {kind} id(s): {', '.join(dupes)}")


# --------------------------------------------------------------------------- loading

_OFFSET_RE = re.compile(r"^\+?(\d+):([0-5]\d):([0-5]\d)$")
_SCENARIO_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def parse_offset(offset: str) -> int:
    """Parse a timeline offset like "+00:10:00" into seconds (600).

    Hours may exceed 23 ("+36:00:00"); minutes and seconds must be 00-59.
    Raises ValueError on anything malformed.
    """
    match = _OFFSET_RE.match(offset.strip())
    if match is None:
        raise ValueError(f"invalid offset {offset!r}: expected '+HH:MM:SS'")
    hours, minutes, seconds = (int(g) for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def scenario_path(name: str, scenario_dir: Path) -> Path:
    """Resolve a scenario name ("baseline") to its YAML file (scenario_dir / "baseline.yaml").

    `name` comes from an HTTP body, so only plain file stems are accepted (letters, digits,
    "_" and "-"); anything else, including "/" and "..", is rejected.
    """
    if not _SCENARIO_NAME_RE.match(name):
        raise ValueError(f"invalid scenario name {name!r}: use letters, digits, '_' or '-'")
    path = scenario_dir / f"{name}.yaml"
    if not path.is_file():
        available = sorted(p.stem for p in scenario_dir.glob("*.yaml"))
        raise FileNotFoundError(
            f"scenario {name!r} not found in {scenario_dir} (available: {', '.join(available)})"
        )
    return path


def load_scenario(name: str, scenario_dir: Path) -> Scenario:
    """Load and validate a scenario by name."""
    data = yaml.safe_load(scenario_path(name, scenario_dir).read_text())
    if not isinstance(data, dict):
        raise ValueError(f"scenario {name!r} is not a YAML mapping")
    return parse_scenario(data)


def parse_scenario(data: dict[str, Any]) -> Scenario:
    """Validate an already-parsed scenario document (used by POST /sim/scenario/load)."""
    return Scenario.model_validate(data)
