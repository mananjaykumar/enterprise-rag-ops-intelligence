import logging
import time
import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.services.observability import get_observability_service

logger = logging.getLogger("api.observability")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Enterprise HTTP tracing and telemetry middleware.

    - Injects unique X-Trace-ID correlation headers.
    - Measures end-to-end request duration.
    - Records spans and structured logging for observability platforms.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = request.headers.get("X-Trace-ID") or f"trc_{uuid.uuid4().hex[:12]}"
        request.state.trace_id = trace_id

        start_time = time.perf_counter()
        obs_service = get_observability_service()

        with obs_service.trace_span(
            name=f"HTTP {request.method} {request.url.path}",
            metadata={
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
                "trace_id": trace_id,
            },
        ) as span:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Injected response correlation headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Response-Time-Ms"] = f"{duration_ms}ms"

            if span and hasattr(span, "update"):
                span.update(
                    metadata={
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    }
                )

            logger.info(
                "[%s] %s %s -> status=%d latency=%.2fms",
                trace_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

            return response
