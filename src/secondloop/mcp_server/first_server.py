"""Chapter 2: one read-only tool over a fixture."""

import asyncio
import json
import sys

from fastmcp import Client, FastMCP

mcp = FastMCP("SecondLoop investigations")

ORDERS = {
    "SL-1042": {
        "order_ref": "SL-1042",
        "store_id": "secondloop-lab",
        "delivery_status": "delivered",
        "sku": "LAP-14-R",
        "replacement_confirmed": False,
    }
}


@mcp.tool(annotations={"readOnlyHint": True})
def get_order_brief(order_ref: str) -> dict:
    """Read a fixture order by its exact SL reference.

    Returns delivery facts, not return eligibility.
    Does not create a return or a replacement.
    """
    order = ORDERS.get(order_ref)
    if order is None:
        return {"ok": False, "code": "not_found"}
    return {"ok": True, "order": dict(order)}


async def check() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert [t.name for t in tools] == [
            "get_order_brief"
        ]
        found = await client.call_tool(
            "get_order_brief", {"order_ref": "SL-1042"}
        )
        assert found.data["ok"] is True
        missing = await client.call_tool(
            "get_order_brief", {"order_ref": "SL-9999"}
        )
        assert missing.data["code"] == "not_found"
        print(json.dumps(found.data, indent=2))


if __name__ == "__main__":
    if "--serve" in sys.argv:
        mcp.run()
    else:
        asyncio.run(check())
