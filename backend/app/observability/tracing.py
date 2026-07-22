"""
OpenTelemetry distributed tracing configuration for HAIOS.
"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

_tracer_provider: TracerProvider | None = None


def configure_tracing(service_name: str = "haios-backend", debug: bool = False) -> None:
    """
    Initialize OpenTelemetry tracing.
    In production, replace ConsoleSpanExporter with an OTLP exporter.
    """
    global _tracer_provider

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    # Export spans to console in debug mode; in production wire up OTLP
    if debug:
        exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _tracer_provider = provider


def instrument_fastapi(app: object) -> None:
    """Attach FastAPI auto-instrumentation to the given app instance."""
    FastAPIInstrumentor.instrument_app(app)  # type: ignore[arg-type]


def get_tracer(name: str) -> trace.Tracer:
    """Return a named tracer for manual span creation."""
    return trace.get_tracer(name)
