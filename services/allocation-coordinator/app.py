import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

AGENT = "allocation-coordinator"
RAG_URL = os.getenv("RAG_URL", "http://rag-service:8080")
EXPLANATION_URL = os.getenv("EXPLANATION_URL", "http://explanation-service:8080")


def call(url, message):
    req = urllib.request.Request(url, data=message.encode(), method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


# Agent loop: perceive -> decide -> act. Ranking and offers go in decide() later.
def perceive(message):
    return message


def decide(observation):
    policy = call(RAG_URL, "hello")                 # policy look-up (RAG)
    explanation = call(EXPLANATION_URL, "hello")    # explanation from the LLM
    return {"reply": f"hit {AGENT}", "rag": policy, "explanation": explanation}


def act(decision):
    return decision


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        message = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode() or "hello"
        body = json.dumps({"agent": AGENT, "received": message, **act(decide(perceive(message)))}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST


print(f"{AGENT} listening on port 8080", flush=True)
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
