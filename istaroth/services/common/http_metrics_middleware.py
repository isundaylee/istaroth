"""HTTP metrics middleware for Prometheus instrumentation."""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from istaroth.services.common import metrics


class HTTPMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records HTTP request count and latency."""

    def __init__(self, app, *, service: str) -> None:
        super().__init__(app)
        self._service = service

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        labels = {
            "service": self._service,
            "method": request.method,
            "path": request.url.path,
            "status": str(response.status_code),
        }
        metrics.http_requests_total.labels(**labels).inc()
        metrics.http_request_duration_seconds.labels(**labels).observe(duration)
        return response
