"""Prometheus metrics shared (copied) by the Python services."""
from prometheus_client import Counter, start_http_server

# Counts every HTTP response, labelled by service and status code (200, 202, 503...).
HTTP_REQUESTS = Counter("hrc_http_requests_total", "HTTP responses sent", ["service", "status"])


def start(port=9100):
    """Expose /metrics on its own port, so scraping never triggers agent behaviour on 8080."""
    start_http_server(port)
