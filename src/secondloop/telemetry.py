"""Tracing setup and the attributes we allow."""

import os
import re

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
)

tracer = trace.get_tracer("secondloop")

ALLOWED = {
    "app.case_id",
    "app.operation_id",
    "app.proposal_id",
    "app.store_id",
    "app.actor",
    "app.result",
    "app.code",
    "app.turn",
    "app.calls",
    "shopify.operation",
    "shopify.cost.actual",
    "shopify.cost.available",
    "gen_ai.request.model",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.response.finish_reasons",
    "gen_ai.tool.name",
}
EMAIL = re.compile(r"[^@\s]+@[^@\s]+")


def safe(attributes: dict) -> dict:
    """Keep allowed keys; mask anything like an email."""
    kept = {}
    for key, value in attributes.items():
        if key not in ALLOWED or value is None:
            continue
        if isinstance(value, str):
            value = EMAIL.sub("[email]", value)[:200]
        kept[key] = value
    return kept


def setup(service: str, exporter=None) -> TracerProvider:
    """Install a provider. Call once per process."""
    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": service}
        )
    )
    if exporter is None and os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    ):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: E501
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter()
    if exporter is not None:
        provider.add_span_processor(
            BatchSpanProcessor(exporter)
        )
    trace.set_tracer_provider(provider)
    return provider
