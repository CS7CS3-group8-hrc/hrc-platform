import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

VERSION = os.getenv("VERSION", "dev")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"service": "hello-python", "version": VERSION, "message": "hello"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()