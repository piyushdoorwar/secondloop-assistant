"""A first-draft interface, kept to measure chapter 5."""

from fastmcp import FastMCP

from secondloop.mcp_server.server import case_brief
from secondloop.ops_client import get_json, ops_http

draft = FastMCP("SecondLoop draft interface")


@draft.tool
def get_order_brief(case_id: str) -> dict:
    """Get order data."""
    brief, error = case_brief(case_id)
    if error:
        return {"error": error}
    return draft_shape(brief)


def draft_shape(brief) -> dict:
    """The chapter 3 brief: one order-level delivery."""
    dates = [
        l.delivered_at
        for l in brief.lines
        if l.delivered_at
    ]
    return {
        "order_id": brief.order_id,
        "order_ref": brief.order_ref,
        "placed_at": brief.placed_at,
        "fulfillment_status": brief.fulfillment_status,
        "delivered_at": max(dates) if dates else None,
        "lines": [
            {
                "sku": l.sku,
                "ordered": l.ordered,
                "current": l.current,
            }
            for l in brief.lines
        ],
        "open_returns": brief.open_returns,
    }


@draft.tool
async def get_replacement_context(case_id: str) -> dict:
    """Get stock and policy."""
    brief, error = case_brief(case_id)
    if error:
        return {"error": error}
    async with ops_http() as http:
        policy = await get_json(
            http, "/policies/damage/3"
        )
        stock = [
            await get_json(http, f"/stock/{l.sku}")
            for l in brief.lines
        ]
    return {"policy": policy, "stock": stock}
