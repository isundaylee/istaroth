"""Shared OpenTelemetry tracing setup for Istaroth services."""

import logging
import os
import pathlib
import typing

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


def setup_file_tracing(
    output_path: pathlib.Path, *, service_name: str
) -> tuple[sdk_trace.TracerProvider, typing.TextIO]:
    """Configure OTel tracing to write spans as JSONL to a local file.

    Unlike :func:`setup_tracing`, this never talks to a collector; spans are
    serialized one-per-line to ``output_path``. Returns the provider and the open
    file handle — the caller must ``provider.shutdown()`` and close the handle.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out = output_path.open("w", encoding="utf-8")
    provider = sdk_trace.TracerProvider(
        resource=resources.Resource.create({"service.name": service_name})
    )
    provider.add_span_processor(
        sdk_trace_export.SimpleSpanProcessor(
            sdk_trace_export.ConsoleSpanExporter(
                out=out, formatter=lambda span: span.to_json(indent=None) + "\n"
            )
        )
    )
    trace.set_tracer_provider(provider)
    return provider, out


def instrument_fastapi_app(app: fastapi.FastAPI) -> None:
    """Instrument a FastAPI app instance with OTel middleware if tracing is enabled."""
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        fastapi_instrumentation.FastAPIInstrumentor().instrument_app(app)


def get_tracer(name: str) -> trace.Tracer:
    """Return an OTel tracer for the given instrumentation name."""
    return trace.get_tracer(name)
