"""Scenario files validate against the models (passes now) and the loaders work (milestone 2)."""

from pathlib import Path

import pytest
import yaml

from simulator.config import SCENARIO_DIR
from simulator.scenario import Scenario, load_scenario, parse_offset

SCENARIO_FILES = sorted(SCENARIO_DIR.glob("*.yaml"))


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=[p.stem for p in SCENARIO_FILES])
def test_scenario_yaml_validates(path: Path) -> None:
    Scenario.model_validate(yaml.safe_load(path.read_text()))


def test_parse_offset() -> None:
    assert parse_offset("+00:10:00") == 600
    assert parse_offset("+01:00:05") == 3605
    with pytest.raises(ValueError):
        parse_offset("ten minutes")


def test_load_scenario_by_name() -> None:
    sc = load_scenario("baseline", SCENARIO_DIR)
    assert sc.name == "baseline"
    assert len(sc.hospitals) == 3
    assert len(sc.ambulances) == 4


def test_load_scenario_rejects_path_traversal() -> None:
    with pytest.raises((FileNotFoundError, ValueError)):
        load_scenario("../pyproject", SCENARIO_DIR)
