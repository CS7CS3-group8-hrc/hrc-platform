"""Environment-variable settings (CLAUDE.md Section 9)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    sim_scenario: str = "baseline"
    sim_autostart: bool = False
    sim_speed: float = Field(default=1.0, gt=0)

    kafka_bootstrap_servers: str | None = None
    kafka_security_protocol: Literal["PLAINTEXT", "SSL"] = "PLAINTEXT"
    ambulance_topic: str = "ambulance.events"

    adt_sink: Literal["log", "http", "kafka"] = "log"
    adt_http_url_template: str | None = None
    adt_topic: str = "his.adt"

    position_publish_every_n_ticks: int = Field(default=1, ge=1)
    road_distance_factor: float = Field(default=1.3, gt=0)

    log_level: str = "INFO"

    scenario_dir: Path = SCENARIO_DIR
