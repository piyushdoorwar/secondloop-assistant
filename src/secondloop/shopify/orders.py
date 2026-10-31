"""Read the facts a support case needs from one order."""

from pydantic import BaseModel

ORDER_BRIEF = """
query OrderBrief($id: ID!) {
  order(id: $id) {
    id
    name
    processedAt
    displayFulfillmentStatus
    lineItems(first: 10) {
      nodes { sku quantity currentQuantity }
    }
    fulfillments(first: 5) {
      displayStatus
      deliveredAt
    }
    returns(first: 5) {
      nodes { id status }
    }
  }
}
"""


class Line(BaseModel):
    sku: str | None
    ordered: int
    current: int


class OrderBrief(BaseModel):
    order_id: str
    order_ref: str
    placed_at: str
    fulfillment_status: str
    delivered_at: str | None
    lines: list[Line]
    open_returns: int


def to_brief(order: dict) -> OrderBrief:
    delivered = [
        f["deliveredAt"]
        for f in order["fulfillments"]
        if f["displayStatus"] == "DELIVERED"
        and f["deliveredAt"]
    ]
    returns = order["returns"]["nodes"]
    return OrderBrief(
        order_id=order["id"],
        order_ref=order["name"],
        placed_at=order["processedAt"],
        fulfillment_status=order[
            "displayFulfillmentStatus"
        ],
        delivered_at=(
            max(delivered) if delivered else None
        ),
        lines=[
            Line(
                sku=n["sku"],
                ordered=n["quantity"],
                current=n["currentQuantity"],
            )
            for n in order["lineItems"]["nodes"]
        ],
        open_returns=sum(
            1 for r in returns if r["status"] == "OPEN"
        ),
    )


def read_order_brief(client, order_id: str):
    data = client.query(ORDER_BRIEF, {"id": order_id})
    order = data.get("order")
    return None if order is None else to_brief(order)
