"""Event sinks (CLAUDE.md Sections 2, 3, 7 and 9).

The engine is synchronous and must not know about Kafka or HTTP. It calls `sink.publish(...)`,
which must return immediately. Network sinks put the event on an asyncio.Queue and a
background task (started by `start()`) does the actual sending.

The engine gets two sinks: one for `ambulance.events` and one for ADT, because ADT_SINK can be
`http` while ambulance events go to Kafka.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from simulator.config import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Envelope:
    """One outbound event plus its routing metadata."""

    key: str  # partition key: vehicleId for ambulance events, hospitalId for ADT
    event: BaseModel
    headers: dict[str, str]  # correlationId, eventId, timestamp (CLAUDE.md 3)


def build_headers(event_id: str, sim_time: datetime, correlation_id: str | None = None) -> dict[str, str]:
    """Kafka headers for an event.

    TODO:
      - eventId = event_id
      - timestamp = sim_time as ISO 8601 UTC with a trailing "Z" (sim time, not wall time!)
      - correlationId = correlation_id or event_id (a new chain starts with its own id)
    """
    raise NotImplementedError


class EventSink(Protocol):
    def publish(self, envelope: Envelope) -> None:
        """Hand off an event. Must not block or raise on transient network errors."""
        ...

    async def start(self) -> None: ...

    async def stop(self) -> None:
        """Flush what's pending, then close connections."""
        ...


class InMemorySink:
    """For tests: records everything published, in order."""

    def __init__(self) -> None:
        self.envelopes: list[Envelope] = []

    def publish(self, envelope: Envelope) -> None:
        self.envelopes.append(envelope)

    @property
    def events(self) -> list[BaseModel]:
        return [e.event for e in self.envelopes]

    def clear(self) -> None:
        self.envelopes.clear()

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class LogSink:
    """Writes each event as one structured JSON log line. Default when Kafka is not configured."""

    def __init__(self, stream: str) -> None:
        self.stream = stream  # "ambulance" or "adt", used in the log record

    def publish(self, envelope: Envelope) -> None:
        """TODO: log.info a JSON line with stream, key, headers and
        envelope.event.model_dump(mode="json", by_alias=True)."""
        raise NotImplementedError

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class KafkaSink:
    """aiokafka producer. Milestone 7."""

    def __init__(self, settings: Settings, topic: str) -> None:
        self.settings = settings
        self.topic = topic
        # TODO: self._queue: asyncio.Queue[Envelope], self._producer, self._task

    def publish(self, envelope: Envelope) -> None:
        """TODO: self._queue.put_nowait(envelope). If the queue is full, drop and count."""
        raise NotImplementedError

    async def start(self) -> None:
        """TODO:
          - AIOKafkaProducer(bootstrap_servers=..., security_protocol=...,
                             ssl_context=create_ssl_context() if SSL, acks="all")
          - await producer.start(); spawn the _drain task
        """
        raise NotImplementedError

    async def _drain(self) -> None:
        """TODO: loop: env = await queue.get(); await producer.send_and_wait(topic,
        value=json bytes, key=env.key.encode(), headers=[(k, v.encode()) for k, v in ...])
        Log and keep going on errors."""
        raise NotImplementedError

    async def stop(self) -> None:
        """TODO: wait for the queue to empty (with a timeout), cancel _drain, producer.stop()."""
        raise NotImplementedError


class HttpSink:
    """POST each ADT event to the hospital's Capacity Agent (ADT_SINK=http). Milestone 7."""

    def __init__(self, url_template: str) -> None:
        self.url_template = url_template  # e.g. "http://capacity-agent.{hospitalId}.svc/..."
        # TODO: self._queue, self._client (httpx.AsyncClient), self._task

    def publish(self, envelope: Envelope) -> None:
        """TODO: queue.put_nowait(envelope)."""
        raise NotImplementedError

    async def start(self) -> None:
        """TODO: create httpx.AsyncClient(timeout=...), spawn _drain."""
        raise NotImplementedError

    async def _drain(self) -> None:
        """TODO: url = url_template.format(hospitalId=env.key); POST JSON with the headers as
        HTTP headers (X-Correlation-Id, X-Event-Id ...). Retry a couple of times, then log."""
        raise NotImplementedError

    async def stop(self) -> None:
        """TODO: drain with timeout, cancel task, close client."""
        raise NotImplementedError


def make_sinks(settings: Settings) -> tuple[EventSink, EventSink]:
    """Choose (ambulance_sink, adt_sink) from settings (CLAUDE.md 9).

    TODO:
      - ambulance: KafkaSink(settings, settings.ambulance_topic) if kafka_bootstrap_servers
                   else LogSink("ambulance")
      - adt: by settings.adt_sink → LogSink("adt") | HttpSink(url_template) | KafkaSink(adt_topic)
             (http without a URL template, or kafka without bootstrap servers → raise ValueError)
    """
    raise NotImplementedError
