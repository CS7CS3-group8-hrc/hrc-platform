"""HIS (EXT-01), read-only to the platform. CLAUDE.md 5.1."""

from __future__ import annotations

from fastapi import APIRouter

from simulator.contracts import BedCensus
from simulator.routes.deps import EngineDep

router = APIRouter(prefix="/his", tags=["HIS (EXT-01)"])


@router.get("/{hospital_id}/census", response_model=BedCensus)
def get_bed_census(hospital_id: str, engine: EngineDep) -> BedCensus:
    """getBedCensus. 404 unknown hospital, 503 while the HIS feed is down.

    TODO: return engine.get_bed_census(hospital_id)
    (UnknownEntity → 404 and HisUnavailable → 503 are mapped by handlers in app.py.)
    """
    raise NotImplementedError
