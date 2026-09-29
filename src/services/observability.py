import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from src.core.config import get_settings

logger = logging.getLogger("observability")
settings = get_settings()


class NullSpan:
    """Fallback span used when Langfuse is disabled or unconfigured."""

    def __init__(self, name: str, parent_id: str | None = None) -> None:
        self.name = name
        self.id = f"local-span-{int(time.time() * 1000)}"
        self.trace_id = f"local-trace-{int(time.time() * 1000)}"
        self.parent_id = parent_id
        self.start_time = time.perf_counter()

    def update(self, **kwargs: Any) -> "NullSpan":
        return self

    def end(self, **kwargs: Any) -> None:
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        logger.debug("[LOCAL TRACE] Span '%s' ended in %.2fms", self.name, duration_ms)

    def score(self, **kwargs: Any) -> None:
        pass


class ObservabilityService:
    """Enterprise observability service providing distributed tracing and telemetry."""

    def __init__(self) -> None:
        self.enabled = bool(
            settings.LANGFUSE_ENABLED
            and settings.LANGFUSE_PUBLIC_KEY
            and settings.LANGFUSE_SECRET_KEY
        )
        self._client = None

        if self.enabled:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                logger.info("Langfuse observability client initialized successfully.")
            except Exception as exc:
                logger.warning(
                    "Failed to initialize Langfuse client. Falling back to local tracing: %s", exc
                )
                self.enabled = False
                self._client = None
        else:
            logger.info("Observability running in Local / NullTracer mode (Langfuse disabled).")

    @contextmanager
    def trace_span(
        self,
        name: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        input_data: Any = None,
    ) -> Generator[Any, None, None]:
        """Context manager creating a trace or top-level span."""
        meta = metadata or {}
        if tenant_id:
            meta["tenant_id"] = tenant_id
        if user_id:
            meta["user_id"] = user_id
        if tags:
            meta["tags"] = tags

        if not self.enabled or self._client is None:
            span = NullSpan(name=name)
            try:
                yield span
            finally:
                span.end()
            return

        try:
            span = self._client.start_observation(
                name=name,
                as_type="span",
                input=input_data,
                metadata=meta,
            )
            try:
                yield span
            finally:
                span.end()
        except Exception as exc:
            logger.error("Langfuse tracing span error: %s", exc)
            yield NullSpan(name=name)

    @contextmanager
    def generation_span(
        self,
        name: str,
        model: str,
        prompt: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[Any, None, None]:
        """Context manager creating an LLM generation observation."""
        if not self.enabled or self._client is None:
            span = NullSpan(name=name)
            try:
                yield span
            finally:
                span.end()
            return

        try:
            gen = self._client.start_observation(
                name=name,
                as_type="generation",
                model=model,
                input=prompt,
                metadata=metadata or {},
            )
            try:
                yield gen
            finally:
                gen.end()
        except Exception as exc:
            logger.error("Langfuse generation span error: %s", exc)
            yield NullSpan(name=name)

    def flush(self) -> None:
        """Flushes queued trace events to the Langfuse backend."""
        if self.enabled and self._client is not None:
            try:
                self._client.flush()
            except Exception as exc:
                logger.error("Failed to flush Langfuse events: %s", exc)


# Singleton instance
_observability_service: ObservabilityService | None = None


def get_observability_service() -> ObservabilityService:
    """Returns singleton instance of the ObservabilityService."""
    global _observability_service
    if _observability_service is None:
        _observability_service = ObservabilityService()
    return _observability_service
