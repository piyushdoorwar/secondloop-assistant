"""The SecondLoop investigation server."""

from typing import Annotated

import anyio
from fastmcp import FastMCP
from pydantic import Field

from secondloop.cases import load_cases
from secondloop.cursors import open_cursor, seal
from secondloop.ops_client import (
    OpsError,
    get_json,
    ops_http,
)
from secondloop.results import failure, ok
from secondloop.shopify.client import ShopifyError
from secondloop.shopify.customers import read_candidates
from secondloop.shopify.factory import admin_client
from secondloop.shopify.orders import read_order_brief

mcp = FastMCP(
    "SecondLoop investigations", version="0.5.0"
)
CASES = load_cases()
PAGE_SIZE = 3

CaseId = Annotated[str, Field(pattern=r"^CASE-\d{1,8}$")]
Cursor = Annotated[str | None, Field(max_length=512)]


def case_brief(case_id: str):
    """Return (brief, None) or (None, error_code)."""
    case = CASES.get(case_id)
    if case is None:
        return None, "case_not_found"
    if case.order_id is None:
        return None, "order_not_linked"
    try:
        brief = read_order_brief(
            admin_client(case.shop), case.order_id
        )
    except ShopifyError as error:
        return None, error.code
    if brief is None:
        return None, "order_not_found"
    return brief, None


@mcp.tool(annotations={"readOnlyHint": True})
def get_order_brief(case_id: CaseId) -> dict:
    """Read the order linked to a support case.

    Returns order, shipment and return facts from
    Shopify, line by line. A line's shipment is
    NOT_SHIPPED, IN_TRANSIT, DELIVERED or another
    carrier status; delivered_at is set only for
    DELIVERED lines. Does not decide return
    eligibility, reserve stock, or create anything.
    """
    brief, error = case_brief(case_id)
    if error:
        return failure(error)
    return ok(brief=brief.model_dump())


@mcp.tool(annotations={"readOnlyHint": True})
def list_candidate_orders(
    case_id: CaseId, cursor: Cursor = None
) -> dict:
    """Recent orders of the case's customer, newest first.

    Use when a case has no linked order, so the
    employee can say which order they mean. Never pick
    one yourself. Returns at most three orders; if
    has_more is true, pass next_cursor to see more.
    """
    case = CASES.get(case_id)
    if case is None or case.customer_id is None:
        return failure("case_not_found")
    after = None
    if cursor:
        try:
            after = open_cursor(case_id, cursor)
        except ValueError:
            return failure("cursor_invalid")
    try:
        page = read_candidates(
            admin_client(case.shop),
            case.customer_id,
            first=PAGE_SIZE,
            after=after,
        )
    except ShopifyError as error:
        return failure(error.code)
    if page is None:
        return failure("case_not_found")
    next_cursor = None
    if page.has_more and page.vendor_cursor:
        next_cursor = seal(case_id, page.vendor_cursor)
    return ok(
        candidates=[
            c.model_dump() for c in page.candidates
        ],
        has_more=page.has_more,
        next_cursor=next_cursor,
    )


@mcp.tool(annotations={"readOnlyHint": True})
async def get_replacement_context(
    case_id: CaseId,
) -> dict:
    """Stock and damage policy for a case's products.

    Covers only the SKUs on the case's order. For each
    SKU, reservation is "held_for_this_case" only if a
    unit is already reserved for this case; available
    stock is not a reservation. Does not reserve a unit
    or request a replacement.
    """
    brief, error = await anyio.to_thread.run_sync(
        case_brief, case_id
    )
    if error:
        return failure(error)
    skus = sorted({l.sku for l in brief.lines if l.sku})
    async with ops_http() as http:
        try:
            current = await get_json(
                http, "/policies/damage"
            )
            policy = await get_json(
                http,
                f"/policies/damage/{current['version']}",
            )
            stock = [
                await get_json(
                    http,
                    f"/stock/{sku}?case_id={case_id}",
                )
                for sku in skus
            ]
        except OpsError as error:
            return failure(error.code)
    return ok(
        policy=policy,
        stock=[stock_fact(s) for s in stock],
    )


def stock_fact(row: dict) -> dict:
    held = row["held_for_case"]
    return {
        "sku": row["sku"],
        "on_hand": row["on_hand"],
        "available": row["available"],
        "reservation": (
            "held_for_this_case" if held else "none"
        ),
    }


if __name__ == "__main__":
    mcp.run()
