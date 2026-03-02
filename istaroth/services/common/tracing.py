"""Shared OpenTelemetry tracing setup for Istaroth services."""

import logging
import os

import fastapi
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc import trace_exporter as otlp_exporter
from opentelemetry.instrumentation import fastapi as fastapi_instrumentation
from opentelemetry.instrumentation import httpx as httpx_instrumentation
from opentelemetry.sdk import resources
from opentelemetry.sdk import trace as sdk_trace
from opentelemetry.sdk.trace import export as sdk_trace_export

logger = logging.getLogger(__name__)


def setup_tracing(service_name: str) -> None:
    """Configure OTel tracing; no-op if OTEL_EXPORTER_OTLP_ENDPOINT is unset."""
    if not (endpoint := os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")):
        return

    provider = sdk_trace.TracerProvider(
        resource=resources.Resource.create({"service.name": service_name})
    )
    provider.add_span_processor(
        sdk_trace_export.BatchSpanProcessor(
            otlp_exporter.OTLPSpanExporter(endpoint=endpoint)
        )
    )
    trace.set_tracer_provider(provider)
    httpx_instrumentation.HTTPXClientInstrumentor().instrument()

    logger.info("Tracing setup completed, sending traces to %s", endpoint)


def instrument_fastapi_app(app: fastapi.FastAPI) -> None:
    """Instrument a FastAPI app instance with OTel middleware if tracing is enabled."""
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        fastapi_instrumentation.FastAPIInstrumentor().instrument_app(app)


def get_tracer(name: str) -> trace.Tracer:
    """Return an OTel tracer for the given instrumentation name."""
    return trace.get_tracer(name)
