# Observability (Prometheus + Grafana)

A shared monitoring stack that is not tied to any one service. Prometheus regularly visits each
service's `/metrics` page and stores the numbers; Grafana draws graphs from them.

```
service /metrics  <--visits every 5s--  Prometheus  <--queries--  Grafana (http://localhost:3001)
kafka -> kafka-exporter /metrics  <------^
```

## Run it

```bash
cp .env.example .env          # then set GRAFANA_ADMIN_PASSWORD in .env (never commit .env)
docker compose -f docker-compose.agents.yml -f docker-compose.observability.yml up -d --build
./load.sh                     # sends traffic so the graphs move (Ctrl+C to stop)
```

- Grafana: http://localhost:3001 (user `admin`), dashboard **HRC > HRC Platform Overview**
- Prometheus: http://localhost:9090, **Status > Targets**: every target should be `UP`

Run both compose files in the **same command**, as above. Both put their services on one shared
Docker network called `hrc-net`.

## Demo: show that monitoring works

1. Run `./load.sh`. All services are green and the message graphs move.
2. `docker compose -f docker-compose.agents.yml stop allocation-coordinator`
   Its status turns **DOWN**, and "Messages waiting to be consumed" climbs, because the agents keep
   publishing and nobody reads (the reply path stops too).
3. `docker compose -f docker-compose.agents.yml start allocation-coordinator`
   The waiting count drains back to 0.

## What is measured today

| Metric | From | Meaning |
|---|---|---|
| `up` | Prometheus | Is the service reachable? |
| `hrc_http_requests_total{service,status}` | every Python service | HTTP responses sent |
| `hrc_kafka_messages_produced_total{service,topic}` | Kafka-using agents | Messages published |
| `hrc_kafka_messages_consumed_total{service,topic}` | Kafka-using agents | Messages read |
| `hrc_kafka_handler_errors_total{service,topic}` | Kafka-using agents | Messages that failed in the handler |
| `kafka_consumergroup_lag`, `kafka_topic_partition_current_offset`, `kafka_brokers` | kafka-exporter | Waiting messages, total messages, broker up |

Python services serve `/metrics` on **port 9100** (separate from their 8080 API on purpose: the agents
treat any request on 8080 as a message, so scraping there would trigger agent behaviour).

## Add a new service to monitoring

1. **Make it serve a `/metrics` page.**
   - Python: copy `services/<any>/metrics.py`, add `prometheus-client` to `requirements.txt`, call `metrics.start()`.
   - Java: Spring Boot Actuator + Micrometer Prometheus registry.
   - Databases and other software: use the standard Prometheus exporter for it (e.g. `postgres-exporter`).
2. **Put the container on the `hrc-net` network.** Services in the agents compose file already are. In any
   other compose file add:
   ```yaml
   networks:
     default:
       name: hrc-net
       external: true      # joins the existing network instead of creating a new one
   ```
3. **Tell Prometheus where it is**: add a file `observability/prometheus/targets/<name>.yml`:
   ```yaml
   - targets: ["my-service:9100"]
     labels: {service: my-service, kind: python-service}
   ```
   Prometheus picks it up within a minute, with no restart.

## Not covered yet

Logs and tracing, alert rules, per-container CPU/memory, and the hospital node (SQL Server, Debezium,
TimescaleDB, Java app). The steps above are how those plug in later.
