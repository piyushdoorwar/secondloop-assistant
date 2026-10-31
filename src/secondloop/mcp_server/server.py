"""The SecondLoop investigation server."""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from secondloop.cases import load_cases
from secondloop.ops_client import (
    OpsError,
    get_json,
    ops_http,
)
from secondloop.shopify.client import ShopifyError
from secondloop.shopify.factory import admin_client
from secondloop.shopify.orders import read_order_brief

mcp = FastMCP(
    "SecondLoop investigations", version="0.4.0"
)
CASES = load_cases()

CaseId = Annotated[str, Field(pattern=r"^CASE-\d{1,8}$")]


@mcp.tool(annotations={"readOnlyHint": True})
def get_order_brief(case_id: CaseId) -> dict:
    """Read the order linked to a support case.

    Returns fulfillment, delivery and return facts from
    Shopify. Does not decide return eligibility, reserve
    stock, or create anything.
    """
    case = CASES.get(case_id)
    if case is None:
        return {"ok": False, "code": "case_not_found"}
    try:
        brief = read_order_brief(
            admin_client(case.shop), case.order_id
        )
    except ShopifyError as error:
        return {"ok": False, "code": error.code}
    if brief is None:
        return {"ok": False, "code": "order_not_found"}
    return {"ok": True, "brief": brief.model_dump()}


@mcp.tool(annotations={"readOnlyHint": True})
async def get_replacement_context(
    case_id: CaseId,
) -> dict:
    """Stock and damage policy for a case's products.

    Covers only the SKUs on the case's order. Reports
    stock on hand and units already held for other
    cases. Does not reserve a unit or request a
    replacement.
    """
    case = CASES.get(case_id)
    if case is None:
        return {"ok": False, "code": "case_not_found"}
    try:
        brief = read_order_brief(
            admin_client(case.shop), case.order_id
        )
    except ShopifyError as error:
        return {"ok": False, "code": error.code}
    if brief is None:
        return {"ok": False, "code": "order_not_found"}
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
                await get_json(http, f"/stock/{sku}")
                for sku in skus
            ]
        except OpsError as error:
            return {"ok": False, "code": error.code}
    return {
        "ok": True,
        "policy": policy,
        "stock": stock,
        "reservation_confirmed": False,
    }


if __name__ == "__main__":
    mcp.run()
