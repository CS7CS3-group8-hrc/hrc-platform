"""The message format like a DTO i guess."""
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class Event:
    type: str
    hospitalId: str
    correlationId: str
    payload: dict
    eventId: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def from_dict(data):
        return Event(type=data.get("type"), hospitalId=data.get("hospitalId"),
                     correlationId=data.get("correlationId"), payload=data.get("payload") or {},
                     eventId=data.get("eventId"), ts=data.get("ts"))

    def to_dict(self):
        return asdict(self)