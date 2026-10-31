"""Chapter 3: the order brief now comes from Shopify."""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from secondloop.cases import load_cases
from secondloop.shopify.client import ShopifyError
from secondloop.shopify.factory import admin_client
from secondloop.shopify.orders import read_order_brief

mcp = FastMCP("SecondLoop investigations")
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


if __name__ == "__main__":
    mcp.run()
