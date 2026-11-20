import json
from http.server import BaseHTTPRequestHandler, HTTPServer

AGENT = "ambulance-coordination-agent"


# Agent loop: perceive -> decide -> act. Real rules and messaging go here later.
def perceive(message):
    return message


def decide(observation):
    return f"hit {AGENT}"


def act(decision):
    return decision


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        message = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode() or "hello"
        reply = act(decide(perceive(message)))
        body = json.dumps({"agent": AGENT, "received": message, "reply": reply}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST


print(f"{AGENT} listening on port 8080", flush=True)
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
