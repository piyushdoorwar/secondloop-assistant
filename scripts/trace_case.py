"""Investigate a case and print its trace as a tree.

python scripts/trace_case.py CASE-17
"""

import asyncio
import os
import sys

from fastmcp import Client
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E501
    InMemorySpanExporter,
)

from secondloop import telemetry

EXPORTER = InMemorySpanExporter()
telemetry.setup("secondloop-host").add_span_processor(
    SimpleSpanProcessor(EXPORTER)
)

from secondloop.host.claude import ClaudeModel  # noqa
from secondloop.host.cli import READ_TOOLS, SYSTEM  # noqa
from secondloop.host.context import investigation  # noqa
from secondloop.host.loop import run  # noqa
from secondloop.mcp_server.server import mcp  # noqa

SHOW = (
    "gen_ai.usage.input_tokens",
    "app.result",
    "shopify.cost.actual",
    "gen_ai.tool.name",
)


def parent_of(span, spans, known):
    """Skip hidden transport spans between client and server."""
    if span.parent is None:
        return None
    if span.parent.span_id in known:
        return span.parent.span_id
    same = [
        x
        for x in spans
        if x is not span
        and x.name == span.name
        and x.context.trace_id == span.context.trace_id
        and x.start_time <= span.start_time
    ]
    return same[-1].context.span_id if same else None


def tree(spans):
    known = {s.context.span_id for s in spans}
    children = {}
    for s in spans:
        parent = parent_of(s, spans, known)
        children.setdefault(parent, []).append(s)

    def walk(parent, depth):
        kids = sorted(
            children.get(parent, []),
            key=lambda s: s.start_time,
        )
        for s in kids:
            ms = (s.end_time - s.start_time) / 1e6
            extra = {
                k: s.attributes[k]
                for k in SHOW
                if k in s.attributes
            }
            print(
                f"{'  ' * depth}{s.name}  {ms:.0f} ms"
                f"  {extra if extra else ''}"
            )
            walk(s.context.span_id, depth + 1)

    walk(None, 0)


async def main(case_id):
    async with Client(mcp) as client:
        messages, _ = await investigation(client, case_id)
        await run(
            ClaudeModel(),
            client,
            messages,
            READ_TOOLS,
            system=SYSTEM,
            case_id=case_id,
        )
    spans = [
        s
        for s in EXPORTER.get_finished_spans()
        if not s.name.startswith(
            ("MCP send", "server/discover", "fastapi.")
        )
    ]
    tree(spans)


if __name__ == "__main__":
    os.environ.setdefault("SECONDLOOP_ENV", "dev")
    os.environ.setdefault("SECONDLOOP_DEV_SUBJECT", "ben")
    asyncio.run(main(sys.argv[1]))
