import logging
import os
import re
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4

import sentry_sdk
import structlog
from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from starlette.responses import JSONResponse

correlation_id = ContextVar("correlation_id", default="")
service = os.getenv("OTEL_SERVICE_NAME", "sirius-app")
configured = False


def enrich(logger, method, event):
    event["service"] = service
    event["correlation_id"] = correlation_id.get()
    span = trace.get_current_span().get_span_context()
    if span.is_valid:
        event["trace_id"] = format(span.trace_id, "032x")
    return event


def setup():
    global configured
    if configured:
        return
    configured = True
    processors = [
        structlog.stdlib.ExtraAdder(), enrich, structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(), foreign_pre_chain=processors,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    structlog.configure(
        processors=processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        provider = TracerProvider(resource=Resource.create({"service.name": service}))
        provider.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces", timeout=3)
        ))
        trace.set_tracer_provider(provider)
    dsn = os.getenv("SENTRY_DSN")
    if dsn:
        sentry_sdk.init(dsn=dsn, send_default_pii=False, traces_sample_rate=0)


def headers():
    carrier = {"X-Correlation-ID": correlation_id.get() or str(uuid4())}
    propagate.inject(carrier)
    return carrier


@contextmanager
def message_context(carrier, name):
    token = correlation_id.set(carrier.get("X-Correlation-ID") or str(uuid4()))
    try:
        with trace.get_tracer(__name__).start_as_current_span(
            name, context=propagate.extract(carrier), kind=trace.SpanKind.CONSUMER
        ) as span:
            span.set_attribute("correlation_id", correlation_id.get())
            yield span
    finally:
        correlation_id.reset(token)


def capture_error(exc):
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("correlation_id", correlation_id.get())
        sentry_sdk.capture_exception(exc)


class CorrelationMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        incoming = dict(scope["headers"]).get(b"x-correlation-id", b"").decode("latin1")
        value = incoming if re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", incoming) else str(uuid4())
        token = correlation_id.set(value)
        scope.setdefault("state", {})["correlation_id"] = value
        started = False
        start = perf_counter()
        status = 500

        async def send_response(message):
            nonlocal status, started
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                message["headers"].append((b"x-correlation-id", value.encode()))
            await send(message)

        try:
            with sentry_sdk.isolation_scope() as sentry_scope:
                sentry_scope.set_tag("correlation_id", value)
                trace.get_current_span().set_attribute("correlation_id", value)
                await self.app(scope, receive, send_response)
        except Exception as exc:
            capture_error(exc)
            logging.getLogger(__name__).exception("http_failed")
            if started:
                raise
            await JSONResponse({"detail": "Внутренняя ошибка сервера"}, status_code=500)(
                scope, receive, send_response
            )
        finally:
            logging.getLogger(__name__).info("http_request", extra={
                "path": scope.get("route").path if scope.get("route") else "unmatched",
                "status": status, "duration_ms": round((perf_counter() - start) * 1000, 2),
            })
            correlation_id.reset(token)


setup()


def configure_worker_logging(**kwargs):
    formatter = logging.getLogger().handlers[0].formatter
    for name in ("celery", "celery.task"):
        for handler in logging.getLogger(name).handlers:
            handler.setFormatter(formatter)
