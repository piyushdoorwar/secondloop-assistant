"""Investigate a case from the command line.

python -m secondloop.host.cli CASE-17
"""

import asyncio
import json
import sys

from fastmcp import Client

from secondloop.host.claude import ClaudeModel
from secondloop.host.context import investigation
from secondloop.host.loop import run
from secondloop.mcp_server.server import mcp

SYSTEM = (
    "You help SecondLoop support staff investigate "
    "customer cases. Check facts with the tools. Keep "
    "answers short and say what is still unknown."
)
READ_TOOLS = {
    "get_order_brief",
    "list_candidate_orders",
    "get_replacement_context",
    "check_return_window",
}


async def main(case_id: str) -> None:
    async with Client(mcp) as client:
        messages, version = await investigation(
            client, case_id
        )
        out = await run(
            ClaudeModel(),
            client,
            messages,
            READ_TOOLS,
            system=SYSTEM,
        )
    print(out.answer)
    print("---", file=sys.stderr)
    for call in out.calls:
        print(
            call["name"],
            json.dumps(call["input"]),
            file=sys.stderr,
        )
    print(
        f"policy v{version}, turns {out.turns}, "
        f"stop {out.stop}, tokens {out.usage}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
