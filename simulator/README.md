# HRC External Systems Simulator

Plays the HIS (EXT-01), Ambulance Tracking (EXT-02) and Travel-Time Source (EXT-04) for the
Hospital Resource Coordination Platform. See [CLAUDE.md](CLAUDE.md) for the full spec.

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest
uvicorn simulator.app:app --reload --port 8080   # http://localhost:8080/docs
```

## Docker

```bash
docker build -t hrc-simulator .
docker run -p 8080:8080 -e SIM_AUTOSTART=true hrc-simulator
```

## Status

Templates only: method bodies raise `NotImplementedError` and carry `TODO` notes. Suggested
order follows the milestones in CLAUDE.md Section 8:

| Milestone | Files |
|---|---|
| 1 Skeleton | done: `contracts.py`, `config.py`, `/health`, Dockerfile, pytest |
| 2 World and clock | `scenario.py` loaders, `world.py` builders, `engine.py` lifecycle/scheduling/step, `sinks.LogSink`, `app.lifespan`, `/sim/*` |
| 3 HIS | `processes.py` HIS handlers, `Hospital.to_census`, `routes/his.py` |
| 4 Ambulances | `geo.py`, `Ambulance` transitions, `_move_ambulances`, `emergency_call`, `routes/tracking.py` GETs |
| 5 Travel | `engine.travel_times/route/get_road_conditions`, `routes/travel.py` |
| 6 Closing the loop | crew messaging in `engine.py`, arrival handlers in `processes.py` |
| 7 Sinks | `KafkaSink`, `HttpSink`, `make_sinks` |
| 8 Injections | `engine._inject_*`, `mass_casualty.yaml` |
| 9 Metrics | `/metrics` |
