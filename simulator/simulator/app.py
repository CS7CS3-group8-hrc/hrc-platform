"""FastAPI app. The lifespan builds the sinks and engine, loads the start-up scenario and runs
the simulation loop in the background (CLAUDE.md 7)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from simulator.config import Settings
from simulator.engine import EngineNotLoaded, HisUnavailable, UnknownEntity
from simulator.routes import control, his, tracking, travel
from simulator.world import InvalidTransition


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start-up and shutdown.

    TODO (milestone 2):
      - configure JSON logging at settings.log_level
      - ambulance_sink, adt_sink = make_sinks(settings); await both .start()
      - engine = Engine(settings, ambulance_sink, adt_sink); app.state.engine = engine
      - engine.load_scenario(load_scenario(settings.sim_scenario, settings.scenario_dir))
      - if settings.sim_autostart: engine.start()
      - task = asyncio.create_task(engine.run_forever())
      - yield
      - task.cancel() (suppress CancelledError); await both sinks' .stop()
    Tests that need an engine can set app.state.engine themselves before making requests.
    """
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="HRC External Systems Simulator",
        version="0.1.0",
        description="Simulates HIS (EXT-01), Ambulance Tracking (EXT-02) and Travel-Time (EXT-04).",
        lifespan=lifespan,
    )
    app.state.settings = settings or Settings()

    app.include_router(his.router)
    app.include_router(tracking.router)
    app.include_router(travel.router)
    app.include_router(control.router)
    app.include_router(control.metrics_router)

    @app.get("/health", tags=["Ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    _register_error_handlers(app)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    """Map engine exceptions to HTTP status codes in one place."""

    @app.exception_handler(UnknownEntity)
    async def _404(_: Request, exc: UnknownEntity) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(HisUnavailable)
    async def _503(_: Request, exc: HisUnavailable) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": str(exc)}, headers={"Retry-After": "30"}
        )

    @app.exception_handler(EngineNotLoaded)
    async def _409_not_loaded(_: Request, exc: EngineNotLoaded) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidTransition)
    async def _409_transition(_: Request, exc: InvalidTransition) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})


app = create_app()
