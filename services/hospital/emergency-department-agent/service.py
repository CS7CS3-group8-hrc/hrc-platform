
import config
from event import Event


class PingService:
    def __init__(self, repository):
        self.repository = repository

    def handle(self, event):
        """Returns the reply Event, or None if the ping is not for this agent."""
        if event.payload.get("target") != config.AGENT or event.hospitalId != config.HOSPITAL_ID:
            return None

        message = f"{event.payload.get('text', 'hello world')} · {config.SUFFIX}"
        try:
            self.repository.save(message, config.AGENT, config.HOSPITAL_ID, event.correlationId)
            status = "PingSaved"
        except Exception as exc:
            status, message = "PingFailed", str(exc)

        print(f"[{config.AGENT}/{config.HOSPITAL_ID}] {event.correlationId}: {status} '{message}'", flush=True)

        return Event(type=status, hospitalId=config.HOSPITAL_ID, correlationId=event.correlationId,
                     payload={"agent": config.AGENT, "message": message})