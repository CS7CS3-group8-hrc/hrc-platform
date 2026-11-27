import json
from http.server import BaseHTTPRequestHandler, HTTPServer

SERVICE = "rag-service"


# Placeholder: later this embeds the question and searches pgvector / S3 policy documents.
def retrieve(question):
    return [{"policy_id": "POL-HELLO-001", "text": "Hello policy: every recommendation is approved by a person."}]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        message = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode() or "hello"
        body = json.dumps({"service": SERVICE, "received": message, "reply": f"hit {SERVICE}", "passages": retrieve(message)}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST


print(f"{SERVICE} listening on port 8080", flush=True)
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
