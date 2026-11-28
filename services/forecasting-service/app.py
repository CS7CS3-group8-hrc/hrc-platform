import json
from http.server import BaseHTTPRequestHandler, HTTPServer

import metrics

SERVICE = "forecasting-service"

# Very simple model: expected ED patients per hour = base rate x scenario multipliers.
# All numbers are placeholders for the skeleton.
BASE_PER_HOUR = {"mater": 8, "beaumont": 8, "st-james": 7, "tallaght": 8, "st-vincents": 7, "connolly": 7}

SCENARIOS = {
    "snow": 1.4,          # road accidents, slips and falls
    "heatwave": 1.15,     # heat stroke, dehydration
    "storm": 1.2,         # injuries from debris
    "flu_season": 1.1,    # breathing problems
    "poor_air": 1.08,     # asthma flare-ups
    "bank_holiday": 1.3,  # alcohol-related injuries
    "road_closure": 1.15, # patients diverted to this hospital
    "concert": 1.5,       # crowd crush, intoxication
}


def predict(hospital, hours, scenarios):
    rate = BASE_PER_HOUR.get(hospital, 7)
    for s in scenarios:
        rate *= SCENARIOS.get(s, 1.0)
    return round(rate * hours, 1)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        if self.path == "/forecast":
            body = json.loads(raw or "{}")
            hospital = body.get("hospital", "mater")
            hours = body.get("hours", 4)
            scenarios = body.get("scenarios", [])
            reply = {"hospital": hospital, "hours": hours, "scenarios": scenarios,
                     "expected_patients": predict(hospital, hours, scenarios)}
        else:
            reply = {"service": SERVICE, "received": raw or "hello", "reply": f"hit {SERVICE}"}
        body = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_request(self, code="-", size="-"):
        metrics.HTTP_REQUESTS.labels(SERVICE, str(code)).inc()
        super().log_request(code, size)

    do_GET = do_POST


metrics.start()
print(f"{SERVICE} listening on port 8080", flush=True)
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
