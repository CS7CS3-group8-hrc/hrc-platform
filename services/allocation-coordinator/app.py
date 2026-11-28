import json
import os
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import metrics

from kafka_bus import REPLIES_TOPIC, REQUESTS_TOPIC, Bus

AGENT = "allocation-coordinator"
RAG_URL = os.getenv("RAG_URL", "http://rag-service:8080")
EXPLANATION_URL = os.getenv("EXPLANATION_URL", "http://explanation-service:8080")
bus = Bus(AGENT)


def call(url, message):
    req = urllib.request.Request(url, data=message.encode(), method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


# Agent loop: perceive -> decide -> act. Ranking and offers go in decide() later.
def perceive(message):
    return message


def decide(observation):
    policy = call(RAG_URL, "hello")                 # policy look-up (RAG), still plain HTTP
    explanation = call(EXPLANATION_URL, "hello")    # explanation from the LLM, still plain HTTP
    return {"reply": f"hit {AGENT}", "rag": policy, "explanation": explanation}


def act(decision):
    return decision


def on_kafka_message(topic, message):
    """Runs for every message on the requests topic: log it and publish a reply."""
    print(f"[{AGENT}] CONSUMED request: {message}", flush=True)
    reply = {"id": str(uuid.uuid4()), "correlation_id": message["id"], "from": AGENT,
             "to": message["from"], "text": f"hit {AGENT}"}
    bus.publish(REPLIES_TOPIC, reply, key=message["id"])


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        message = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode() or "hello"
        body = json.dumps({"agent": AGENT, "received": message, **act(decide(perceive(message)))}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_request(self, code="-", size="-"):
        metrics.HTTP_REQUESTS.labels(AGENT, str(code)).inc()
        super().log_request(code, size)

    do_GET = do_POST


bus.subscribe([REQUESTS_TOPIC], on_kafka_message)
metrics.start()
print(f"{AGENT} listening on port 8080", flush=True)
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
