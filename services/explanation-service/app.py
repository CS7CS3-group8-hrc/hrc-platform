import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

SERVICE = "explanation-service"
VLLM_URL = os.getenv("VLLM_URL", "http://host.docker.internal:8010/v1")
VLLM_MODEL = os.getenv("VLLM_MODEL", "mlx-community/Qwen2.5-0.5B-Instruct-4bit")


def ask_llm(prompt):
    """Send one prompt to vLLM's OpenAI-compatible API and return the answer text."""
    payload = {"model": VLLM_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 20}
    req = urllib.request.Request(
        f"{VLLM_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"LLM not reachable: {exc}"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        message = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode() or "hello"
        answer = ask_llm(f"Reply to '{message}' in 5 words.")
        body = json.dumps({"service": SERVICE, "received": message, "reply": f"hit {SERVICE}", "llm": answer}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST


print(f"{SERVICE} listening on port 8080", flush=True)
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
