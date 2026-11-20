import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

ALLOCATION_URL = os.getenv("ALLOCATION_URL", "http://allocation-coordinator:8080")
AGENT = "ambulance-coordination-agent"


# Agent loop: perceive -> decide -> act. Real rules and messaging go here later.
def perceive(message):
    return message


def ask_allocation(message):
    """Send a message to the Allocation Coordinator over HTTP and return its reply."""
    req = urllib.request.Request(ALLOCATION_URL, data=message.encode(), method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["reply"]


def decide(observation):
    allocation = ask_allocation(f"hello from {AGENT}")   # later: requestAllocation
    return {"reply": f"hit {AGENT}", "allocation_coordinator": allocation}


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
