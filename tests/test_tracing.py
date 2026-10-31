import pytest
from fastmcp import Client
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E501
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
)

from secondloop import telemetry
from secondloop.host.loop import run
from secondloop.mcp_server.server import mcp
from test_host_loop import READS, Scripted, call, say, use

pytestmark = pytest.mark.anyio
EXPORTER = InMemorySpanExporter()
PROVIDER = telemetry.setup("test")
PROVIDER.add_span_processor(SimpleSpanProcessor(EXPORTER))


@pytest.fixture
def spans(monkeypatch):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    EXPORTER.clear()
    return EXPORTER


async def investigate():
    model = Scripted(
        use(
            call(
                "get_order_brief", {"case_id": "CASE-17"}
            )
        ),
        say("SL-1042 was delivered."),
    )
    async with Client(mcp) as client:
        await run(
            model, client, "q", READS, case_id="CASE-17"
        )


async def test_one_trace_from_host_to_shopify(spans):
    await investigate()
    found = {
        s.name: s for s in spans.get_finished_spans()
    }
    root = found["case.investigate"]
    for name in (
        "model.turn",
        "tools/call get_order_brief",
        "shopify OrderBrief",
    ):
        assert found[name].context.trace_id == (
            root.context.trace_id
        )
    assert root.attributes["app.case_id"] == "CASE-17"


async def test_no_customer_text_in_any_attribute(spans):
    await investigate()
    values = [
        str(v)
        for s in spans.get_finished_spans()
        for v in s.attributes.values()
    ]
    assert not any(
        telemetry.EMAIL.search(v) for v in values
    )
    assert not any("Elena" in v for v in values)


def test_unknown_keys_are_dropped():
    kept = telemetry.safe(
        {
            "app.case_id": "CASE-17",
            "customer.email": "elena.ruiz@example.com",
            "app.code": "sent to elena.ruiz@example.com",
        }
    )
    assert kept == {
        "app.case_id": "CASE-17",
        "app.code": "sent to [email]",
    }
