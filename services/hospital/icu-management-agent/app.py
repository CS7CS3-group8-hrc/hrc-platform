"""Entry point: main class"""
import threading

import config
from event import Event
from kafka_bus import Bus
from repository import PingRepository
from service import PingService

bus = Bus(f"{config.AGENT}-{config.HOSPITAL_ID}")
service = PingService(PingRepository(config.NODE_DB_URL))


def on_message(topic, data):
    reply = service.handle(Event.from_dict(data))
    if reply:
        bus.publish(config.PING_REPLIES_TOPIC, reply.to_dict(), key=config.HOSPITAL_ID)


if __name__ == "__main__":
    bus.subscribe([config.PING_REQUESTS_TOPIC], on_message)
    print(f"{config.AGENT} ({config.HOSPITAL_ID}) waiting for pings", flush=True)
    threading.Event().wait()              # keep running; the Kafka consumer is a background thread