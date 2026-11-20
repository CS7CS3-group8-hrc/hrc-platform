"""Tiny Kafka helper shared (copied) by the agents. JSON in, JSON out."""
import json
import os
import threading
import time

from confluent_kafka import Consumer, Producer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
REQUESTS_TOPIC = "hrc.hello.requests"
REPLIES_TOPIC = "hrc.hello.replies"


class Bus:
    def __init__(self, service):
        self.service = service
        self.producer = Producer({"bootstrap.servers": BOOTSTRAP, "client.id": service})

    def publish(self, topic, message, key=None):
        """Send a dict to a topic as JSON. Blocks until Kafka has acknowledged it."""
        self.producer.produce(topic, key=key, value=json.dumps(message).encode())
        if self.producer.flush(10) > 0:
            raise RuntimeError(f"could not deliver message to {topic} (is Kafka up?)")
        print(f"[{self.service}] produced to {topic}: {message}", flush=True)

    def subscribe(self, topics, handler):
        """Start a background thread that calls handler(topic, message_dict) for each message."""
        threading.Thread(target=self._loop, args=(topics, handler), daemon=True).start()

    def _loop(self, topics, handler):
        consumer = Consumer({
            "bootstrap.servers": BOOTSTRAP,
            "group.id": self.service,           # one consumer group per service
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        })
        consumer.subscribe(topics)
        print(f"[{self.service}] consuming {topics}", flush=True)
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"[{self.service}] kafka error: {msg.error()}", flush=True)
                time.sleep(1)
                continue
            try:
                handler(msg.topic(), json.loads(msg.value()))
            except Exception as exc:            # a bad message must not kill the consumer
                print(f"[{self.service}] handler error: {exc}", flush=True)
