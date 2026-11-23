import json
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

from kafka_bus import REPLIES_TOPIC, REQUESTS_TOPIC, Bus

AGENT = "patient-transfer-agent"
bus = Bus(AGENT)


# Agent loop: perceive -> decide -> act. Real rules go in decide() later.
def perceive(message):
    return message


def decide(observation):
    # Build the message to hand to the Allocation Coordinator (via Kafka, not HTTP).
    return {"id": str(uuid.uuid4()), "from": AGENT, "text": observation}


def act(decision):
    bus.publish(REQUESTS_TOPIC, decision, key=decision["id"])
    return decision


def on_kafka_message(topic, message):
    """Runs for every message on the replies topic; only react to replies addressed to us."""
    if message.get("to") == AGENT:
        print(f"[{AGENT}] CONSUMED reply: {message}", flush=True)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        message = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode() or "hello"
        try:
            sent = act(decide(perceive(message)))
            status, body = 202, {"agent": AGENT, "received": message, "status": "published to Kafka",
                                 "topic": REQUESTS_TOPIC, "correlation_id": sent["id"]}
        except Exception as exc:
            status, body = 503, {"agent": AGENT, "received": message, "error": str(exc)}
        out = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    do_GET = do_POST


bus.subscribe([REPLIES_TOPIC], on_kafka_message)
print(f"{AGENT} listening on port 8080", flush=True)
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
