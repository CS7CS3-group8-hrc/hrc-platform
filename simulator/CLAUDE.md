# CLAUDE.md: External Systems Simulator (Group 8, Hospital Resource Coordination Platform)

This file gives Claude Code the context and spec for building the **simulator** thin slice. Put it at the root of the `simulator/` folder. Read all of it before writing code.

---

## 1. What this service is

The Autonomous Hospital Resource Coordination Platform (CS7CS3 group project, Group 8) coordinates beds, ambulances and transfers across hospitals with AI agents. A human approves every significant decision.

The platform reads from **external systems** it does not own. In the prototype, this simulator provides those external systems **through the same interface the real ones would have**. The platform's agents must not be able to tell the difference.

The simulator plays:

| ID | External system | In scope |
|---|---|---|
| EXT-01 | Hospital Information System (HIS), one per hospital | Yes |
| EXT-02 | Ambulance Tracking System (GPS and crew terminal) | Yes |
| EXT-04 | Travel-Time Source (maps and traffic) | Yes |
| EXT-03 | Rostering System | **No** (UC-07 dropped from the architecture) |

It also plays **the world**: patients arriving, beds filling and emptying, incidents, ambulance crews, hospital staff admitting patients, and failures such as a feed going down.

### What it must NOT do

- Do not simulate the platform's agents, the Allocation Coordinator, approvals, forecasting or the dashboard. Those are the real system under test.
- Do not accept writes to the HIS from the platform. The platform's access to the HIS is **read-only** (except the optional transfer summary import, which is out of scope here).
- Do not produce realistic patient-identifiable data. Use synthetic references only, such as `SIM-PT-000123`.
- Do not implement real HL7 v2 or FHIR. Use the simple JSON shapes in Section 5.
- No road-network simulation (SUMO is future work). Use straight-line distance and an average speed.

---

## 2. Tech stack (fixed by the architecture document)

- Python 3.12, FastAPI, Uvicorn, Pydantic v2
- Kafka (TLS in production). Use `aiokafka` as the client.
- asyncio for the simulation loop
- pytest (with pytest-asyncio) for tests
- Docker image; later deployed by Helm to Kubernetes (local cluster in development, Amazon EKS for the demo)
- Config through environment variables (Section 9)

Kafka must be **optional**. If `KAFKA_BOOTSTRAP_SERVERS` is unset, events are written to the console log instead, so the simulator runs standalone before the rest of the platform exists.

---

## 3. Platform context you need

- **Message Broker:** Kafka. Every event carries headers `correlationId`, `eventId` (UUID) and `timestamp` (ISO 8601 UTC). Consumers are idempotent on `eventId`, so duplicates are harmless.
- **Topic used by this service:** `ambulance.events` (event types `PositionUpdate` and `CrewResponse`). Partition key: `vehicleId`.
- **Hospital Capacity Agent** (one per hospital) consumes HIS ADT events in its `onHisEvent` handler. It calls `getBedCensus` to build capacity reports and to reconcile after an outage. When an admission matches an open hold, it publishes `AdmissionMatched`, which closes the placement or transfer.
- **Ambulance Coordination Agent** calls `getAllVehicles`, `getVehicleStatus`, `sendCrewMessage` and `getCrewResponse`, and consumes `PositionUpdate` and `CrewResponse`.
- **Allocation Coordinator** calls `getTravelTimes` to rank hospitals. **Ambulance Coordination Agent** calls `getRoute` for routes and ETAs.
- **Freshness thresholds** the platform applies: ED 5 min, ICU 15 min, theatre 30 min, ambulance position 60 s. Data older than this is labelled Delayed or Stale. The simulator's fault injection should be able to trigger these labels.

---

## 4. Simulation model

### 4.1 Clock

- One simulation clock. `sim_time` starts at the scenario's `startTime`.
- Speed multiplier (default 1.0; for example 10.0 means 10 sim seconds pass per real second). It can be changed at runtime.
- States: `STOPPED`, `RUNNING`, `PAUSED`.
- Fixed tick of **1 sim second** for movement. Scheduled events sit in a priority queue (`heapq`) keyed by sim time and processed in order at each tick.
- All randomness comes from one `random.Random(seed)` instance owned by the engine. **The same scenario and seed must produce the same event sequence.** Never use the module-level `random` functions or wall-clock time in simulation logic.
- Every event carries both `simTime` and `wallTime`. Use `simTime` as the event's `timestamp`, so the platform's freshness logic works under speed-up.

### 4.2 World state

**Hospital:** `hospitalId`, `name`, `lat`, `lon`, `wards[]`, `hisFeedOnline` (bool).

**Ward:** `wardId`, `department` (`ED` | `ICU` | `GENERAL` | `THEATRE_RECOVERY`), `beds[]`.

**Bed:** `bedId`, `status` (`FREE` | `OCCUPIED` | `OUT_OF_SERVICE`), `patientRef` (nullable), `occupiedSince` (nullable).

**Ambulance:** `vehicleId`, `baseLat`, `baseLon`, `lat`, `lon`, `speedKmh`, `heading`, `status`, `targetLat`/`targetLon` (nullable), `destinationHospitalId` (nullable), `placementId` (nullable), `patientRef` (nullable), `patientCategory` (nullable), `telemetryOnline` (bool), `lastPositionAt`.

Ambulance status values:
`AVAILABLE` → `EN_ROUTE_TO_SCENE` → `AT_SCENE` → `AWAITING_DESTINATION` → `TRANSPORTING` → `AT_HOSPITAL` → `RETURNING` → `AVAILABLE`.

`AWAITING_DESTINATION` is the important one. It means a patient is on board and the dispatcher must request a destination on the platform's dashboard (UC-04).

### 4.3 Invariants (enforce in code and test)

- Occupied beds in a ward never exceed total beds.
- A bed has a `patientRef` if and only if it is `OCCUPIED`.
- An ambulance has a `patientRef` only in `AWAITING_DESTINATION`, `TRANSPORTING` or `AT_HOSPITAL`.
- An event is never emitted for a hospital whose HIS feed is offline (it is dropped, not queued, matching a real outage). `getBedCensus` for that hospital returns HTTP 503.

### 4.4 Background processes

- **Admissions** per department follow a Poisson process with a rate per hour from the scenario. Each admission picks a random FREE bed in that department. If none is free, it records a `capacity_full` counter and drops the arrival.
- **Length of stay** is drawn from a lognormal distribution with a mean per department from the scenario. A discharge (`A03`) is scheduled at admission time.
- **Internal transfers** (`A02`, for example ED to ICU) occur with a configurable probability per ED admission. Leave this off by default.

### 4.5 Ambulance movement

- Each tick, a moving ambulance advances toward its target along the straight line at `speedKmh` (default 60, configurable; can be scaled by a road-condition congestion factor).
- Use haversine distance. On arrival (within 50 m), snap to the target and change status.
- Publish a `PositionUpdate` for every ambulance with telemetry online **once per sim second**. If that is too chatty at high speed multipliers, allow `POSITION_PUBLISH_EVERY_N_TICKS`.
- `AT_SCENE` lasts a random 5–15 sim minutes, then the patient is loaded and the status becomes `AWAITING_DESTINATION`. The ambulance waits there until it receives a destination.
- `AT_HOSPITAL` lasts 10 sim minutes (handover), then `RETURNING` to base, then `AVAILABLE`.

### 4.6 Closing the loop (core of the thin slice)

1. The Ambulance Coordination Agent calls `sendCrewMessage(vehicleId, {type: DESTINATION, hospitalId, placementId, department})`.
2. The simulated crew answers after a random 5–20 sim seconds: `ACKNOWLEDGED` (default) or `REJECTED` (if a `crew_reject_next` injection is armed for that vehicle). The `CrewResponse` is published to `ambulance.events` and also stored for `getCrewResponse`.
3. On `ACKNOWLEDGED`, the status becomes `TRANSPORTING` and the ambulance drives to the hospital's coordinates.
4. On arrival, the status becomes `AT_HOSPITAL`, and the simulator plays the hospital staff: after a short delay it emits an **A01 admission** at that hospital in the requested department, into a FREE bed. The ADT message carries the `placementId` from the crew message so the Capacity Agent can match the admission to its hold (see open question Q2).
5. `REROUTE` or `REDIRECT` messages for a vehicle already `TRANSPORTING` change its destination after the crew acknowledges.

If no FREE bed exists in that department on arrival, do not invent one. Log a warning `arrival_no_free_bed`, increment a counter, and admit nothing. This exposes a platform bug or a stale hold, which is exactly what the demo should reveal.

---

## 5. API contracts

All shapes are Pydantic models in `simulator/contracts.py`. That file is the single source of truth and may later move into a shared package used by the agents. **Do not change a field name or type in `contracts.py` without flagging it in your summary**, because other teammates' code depends on it.

All timestamps are ISO 8601 UTC strings. All IDs are strings.

### 5.1 HIS (EXT-01): read-only to the platform

`GET /his/{hospitalId}/census` → `BedCensus` (the `getBedCensus` API)

```json
{
  "hospitalId": "H1",
  "asOf": "2026-11-20T10:00:00Z",
  "wards": [
    {
      "wardId": "H1-ICU",
      "department": "ICU",
      "totalBeds": 12,
      "occupiedBeds": 9,
      "outOfServiceBeds": 0,
      "beds": [{"bedId": "H1-ICU-01", "status": "OCCUPIED"}]
    }
  ]
}
```

Census never includes `patientRef`.

**ADT push** (the `sendAdtEvent` API). The simulator pushes each event to the sink chosen by `ADT_SINK` (Section 9):

```json
{
  "eventId": "uuid",
  "eventType": "A01",
  "hospitalId": "H1",
  "wardId": "H1-ICU",
  "bedId": "H1-ICU-03",
  "department": "ICU",
  "fromWardId": null,
  "fromBedId": null,
  "patientRef": "SIM-PT-000123",
  "placementId": null,
  "occurredAt": "2026-11-20T10:00:05Z"
}
```

`eventType`: `A01` admit, `A02` transfer (uses `fromWardId` and `fromBedId`), `A03` discharge. `placementId` is set only for admissions that result from a platform placement (Section 4.6).

### 5.2 Ambulance Tracking (EXT-02)

- `GET /tracking/vehicles` → `List[VehicleStatus]` (`getAllVehicles`)
- `GET /tracking/vehicles/{vehicleId}` → `VehicleStatus` (`getVehicleStatus`); 404 if unknown
- `POST /tracking/vehicles/{vehicleId}/messages` with body `CrewMessage` → `MessageReceipt` (`sendCrewMessage`)
- `GET /tracking/messages/{messageId}/response` → `CrewResponse`, or 404 if not answered yet (`getCrewResponse`)

```json
// VehicleStatus
{
  "vehicleId": "A1",
  "lat": 53.3438, "lon": -6.2546,
  "speedKmh": 58.2, "heading": 270.0,
  "status": "TRANSPORTING",
  "destinationHospitalId": "H2",
  "placementId": "PL-42",
  "patientCategory": "TRAUMA",
  "online": true,
  "updatedAt": "2026-11-20T10:00:05Z"
}

// CrewMessage (request body)
{"messageId": "uuid", "type": "DESTINATION", "hospitalId": "H2", "placementId": "PL-42", "department": "ED", "note": null}

// MessageReceipt
{"messageId": "uuid", "vehicleId": "A1", "status": "DELIVERED"}

// CrewResponse
{"messageId": "uuid", "vehicleId": "A1", "response": "ACKNOWLEDGED", "reason": null, "respondedAt": "..."}
```

`CrewMessage.type`: `DESTINATION` | `REROUTE` | `REDIRECT`. `MessageReceipt.status` is `QUEUED` when the vehicle's telemetry is offline. Queued messages are delivered when it comes back online.

**Kafka `ambulance.events`** (the `publishPositionUpdate` API):

```json
// PositionUpdate
{
  "eventType": "PositionUpdate",
  "eventId": "uuid",
  "vehicleId": "A1",
  "lat": 53.3438, "lon": -6.2546,
  "speedKmh": 58.2, "heading": 270.0,
  "status": "TRANSPORTING",
  "destinationHospitalId": "H2",
  "placementId": "PL-42",
  "timestamp": "2026-11-20T10:00:05Z"
}
```

`CrewResponse` events use the same topic with `"eventType": "CrewResponse"` plus the `CrewResponse` fields.

### 5.3 Travel-Time Source (EXT-04)

- `POST /travel/times` with body `{origin: {lat, lon}, destinations: [{id, lat, lon}], vehicleType}` → `List[TravelTime]` (`getTravelTimes`)
- `POST /travel/route` with body `{origin, destination, vehicleType}` → `Route` (`getRoute`)
- `GET /travel/conditions/{areaId}` → `List[RoadCondition]` (`getRoadConditions`)

```json
// TravelTime
{"destinationId": "H2", "distanceKm": 4.8, "durationSeconds": 360, "source": "SIMULATED_ESTIMATE"}

// Route
{"distanceKm": 4.8, "durationSeconds": 360, "path": [[53.34, -6.25], [53.35, -6.26]], "source": "SIMULATED_ESTIMATE"}

// RoadCondition
{"areaId": "dublin", "conditionId": "RC-1", "type": "CONGESTION", "factor": 1.5, "until": "..."}
```

Duration = haversine distance × `ROAD_DISTANCE_FACTOR` (default 1.3, to approximate roads) ÷ average speed × active congestion factor. `path` is the straight line sampled every ~200 m. `vehicleType` is accepted but only `AMBULANCE` changes the speed.

### 5.4 Simulator control (for the team and demos, not part of the platform)

Prefix `/sim`:

- `POST /sim/scenario/load` with body `{name}` or a scenario document → loads and resets the world (`STOPPED`)
- `POST /sim/start`, `POST /sim/pause`, `POST /sim/reset`
- `POST /sim/speed` with body `{multiplier}`
- `POST /sim/inject` with body `{type, params}` → applies an injection now (types in Section 6)
- `GET /sim/state` → clock, status, counters, all hospitals (with patientRefs) and ambulances
- `GET /health` → liveness for Kubernetes
- `GET /metrics` → Prometheus metrics (events emitted per type, ticks, tick lag, counters such as `capacity_full` and `arrival_no_free_bed`)

---

## 6. Scenarios

YAML files in `simulator/scenarios/`. Loaded and validated with Pydantic.

```yaml
name: baseline
seed: 42
startTime: "2026-11-20T08:00:00Z"
region: dublin
defaults:
  ambulanceSpeedKmh: 60
hospitals:
  - id: H1
    name: "Hospital North"
    lat: 53.3900
    lon: -6.2230
    wards:
      - {id: H1-ED,  department: ED,      beds: 20, initialOccupancy: 0.7}
      - {id: H1-ICU, department: ICU,     beds: 10, initialOccupancy: 0.8}
      - {id: H1-GEN, department: GENERAL, beds: 60, initialOccupancy: 0.85}
  # H2, H3 similar
background:
  admissionsPerHour: {ED: 6, ICU: 0.5, GENERAL: 3}
  meanLengthOfStayHours: {ED: 4, ICU: 72, GENERAL: 96}
ambulances:
  - {id: A1, baseLat: 53.3498, baseLon: -6.2603}
  # A2..A4
injections: []   # timeline, see below
```

Injection types (usable in the scenario timeline as `{at: "+00:10:00", type, params}` and through `/sim/inject`):

| Type | Params | Effect |
|---|---|---|
| `emergency_call` | `lat, lon, patientCategory` | Nearest AVAILABLE ambulance goes to the scene (Section 4.5) |
| `mass_casualty` | `lat, lon, casualties, categories{TRAUMA: 0.6, BURNS: 0.1, ...}` | Creates N patients at the scene; ambulances are dispatched to it as they become available |
| `his_feed_down` | `hospitalId, durationMinutes` | That hospital's ADT stops and census returns 503; restored after the duration |
| `telemetry_offline` | `vehicleId, durationMinutes` | No PositionUpdates; crew messages are QUEUED |
| `road_condition` | `areaId, factor, durationMinutes` | Slows travel and changes travel-time estimates |
| `crew_reject_next` | `vehicleId, reason` | The next crew message to that vehicle is REJECTED |
| `beds_out_of_service` | `hospitalId, department, count` | Marks FREE beds OUT_OF_SERVICE (equipment or infrastructure failure, Scenario 3) |

Ship two scenarios: `baseline.yaml` (3 hospitals, 4 ambulances, background load, two `emergency_call`s in the first 10 minutes) and `mass_casualty.yaml` (baseline plus a `mass_casualty` of 15 at minute 10 and `beds_out_of_service` at one hospital's ICU at minute 25).

Use made-up hospital names. Coordinates around Dublin are fine.

---

## 7. Project layout

```
simulator/
  CLAUDE.md
  pyproject.toml
  Dockerfile
  README.md
  simulator/
    __init__.py
    app.py            # FastAPI app, lifespan starts and stops the engine and producers
    config.py         # env var settings (pydantic-settings)
    contracts.py      # all request, response and event models (Section 5)
    engine.py         # clock, tick loop, event queue, seeded RNG, injections
    world.py          # Hospital, Ward, Bed, Ambulance and state transitions
    processes.py      # background admissions and discharges, scene times
    geo.py            # haversine, interpolation, heading
    scenario.py       # YAML loading and validation
    sinks.py          # EventSink interface: KafkaSink, HttpSink, LogSink
    routes/
      his.py
      tracking.py
      travel.py
      control.py
  scenarios/
    baseline.yaml
    mass_casualty.yaml
  tests/
```

Keep the engine independent of FastAPI and Kafka: it emits events to an `EventSink` interface, so tests can use an in-memory sink.

---

## 8. Build order (milestones)

Finish and test each milestone before starting the next. After each one, summarise what works and how to try it.

1. **Skeleton:** project layout, config, `contracts.py`, `/health`, Dockerfile, pytest set up.
2. **World and clock:** load `baseline.yaml`, build the world, run the tick loop with speed control and pause. `/sim/state` shows it. LogSink only.
3. **HIS:** background admissions and discharges emitting ADT events; `GET /his/{id}/census`. Invariant tests.
4. **Ambulances:** movement, statuses, `emergency_call`, PositionUpdate events, tracking GET endpoints.
5. **Travel time:** `/travel/times`, `/travel/route`, `/travel/conditions`.
6. **Closing the loop:** `sendCrewMessage`, crew responses, transport, arrival admission with `placementId`. An end-to-end test drives this through the HTTP API alone.
7. **Kafka and HTTP sinks:** `KafkaSink` for `ambulance.events` (with headers and partition key), ADT sink as configured. Still runs without Kafka.
8. **Injections and the mass-casualty scenario,** including fault injection.
9. **Metrics** (`/metrics`) and README with demo instructions.

---

## 9. Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `SIM_SCENARIO` | `baseline` | Scenario loaded at start-up |
| `SIM_AUTOSTART` | `false` | Start the clock on start-up |
| `SIM_SPEED` | `1.0` | Initial speed multiplier |
| `KAFKA_BOOTSTRAP_SERVERS` | unset | If unset, use LogSink for Kafka events |
| `KAFKA_SECURITY_PROTOCOL` | `PLAINTEXT` | `SSL` in the cluster |
| `AMBULANCE_TOPIC` | `ambulance.events` | |
| `ADT_SINK` | `log` | `log`, `http` or `kafka` |
| `ADT_HTTP_URL_TEMPLATE` | unset | For `http`, e.g. `http://capacity-agent.{hospitalId}.svc/internal/v1/his/events` |
| `ADT_TOPIC` | `his.adt` | For `kafka`; partition key = `hospitalId` |
| `POSITION_PUBLISH_EVERY_N_TICKS` | `1` | |
| `ROAD_DISTANCE_FACTOR` | `1.3` | |
| `LOG_LEVEL` | `INFO` | Structured JSON logs (Fluent Bit collects them) |

---

## 10. Testing requirements

- **Determinism:** run the same scenario twice with the same seed for N sim minutes using an in-memory sink; the event sequences must be identical (ignoring UUIDs and wall time, or generate UUIDs from the seeded RNG).
- **Invariants** (Section 4.3) checked after every tick in a long randomised test.
- **Geo:** haversine against a known distance; an ambulance reaches its target within the expected number of ticks.
- **Contracts:** every endpoint returns data that validates against `contracts.py`; FastAPI's OpenAPI schema builds.
- **Closed loop:** load baseline, inject `emergency_call`, run to `AWAITING_DESTINATION`, call `sendCrewMessage`, run to arrival, and assert an A01 with the matching `placementId` was emitted and the bed count changed.
- **Faults:** `his_feed_down` makes census return 503 and stops ADT events; `telemetry_offline` stops PositionUpdates and queues crew messages.

Tests must not need Kafka or network access. Drive the engine by stepping ticks directly rather than sleeping.

---

## 11. Open questions (use the stated default, flag in your summary)

- **Q1: How ADT events reach the Capacity Agent.** The architecture document has no Kafka topic for HIS events. Default: make it configurable (`ADT_SINK`), with `log` for now. To be agreed with the Hospital Capacity Agent owner.
- **Q2: How an admission is matched to a hold.** Default: the A01 carries `placementId` from the crew message. To be agreed with the Capacity Agent and Ambulance Coordination Agent owners.
- **Q3: Whether the Bed Manager blocking a held bed in the HIS should be simulated.** Default: no. The arrival takes any FREE bed in the department.
- **Q4: How the dispatcher learns a patient is waiting.** Default: through `AWAITING_DESTINATION` in VehicleStatus and PositionUpdate; the dashboard reads it from the Ambulance Coordination Agent.

---

## 12. Conventions

- Type hints everywhere; `ruff` and `mypy` clean.
- No global mutable state outside the engine instance.
- Structured logs with `simTime`, `eventType` and IDs. Never log anything that looks like real patient data.
- Small commits per milestone with clear messages.
- If something in this file is ambiguous, choose the simplest option that keeps the API contracts stable, and say what you chose.
