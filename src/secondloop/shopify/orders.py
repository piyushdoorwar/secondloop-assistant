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
      nodes {
        id sku quantity currentQuantity
        unfulfilledQuantity
      }
    }
    fulfillments(first: 5) {
      displayStatus
      deliveredAt
      fulfillmentLineItems(first: 10) {
        nodes { lineItem { id } }
      }
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
    unshipped: int
    shipment: str
    delivered_at: str | None


class OrderBrief(BaseModel):
    order_id: str
    order_ref: str
    placed_at: str
    fulfillment_status: str
    lines: list[Line]
    open_returns: int


def shipments_by_line(order: dict) -> dict:
    """Map line item ID to its latest fulfillment."""
    found = {}
    for f in order["fulfillments"]:
        for n in f["fulfillmentLineItems"]["nodes"]:
            found[n["lineItem"]["id"]] = f
    return found


def to_line(node: dict, shipments: dict) -> Line:
    f = shipments.get(node["id"])
    status = f["displayStatus"] if f else "NOT_SHIPPED"
    delivered = (
        f["deliveredAt"]
        if f and status == "DELIVERED"
        else None
    )
    return Line(
        sku=node["sku"],
        ordered=node["quantity"],
        current=node["currentQuantity"],
        unshipped=node["unfulfilledQuantity"],
        shipment=status,
        delivered_at=delivered,
    )


def to_brief(order: dict) -> OrderBrief:
    shipments = shipments_by_line(order)
    returns = order["returns"]["nodes"]
    return OrderBrief(
        order_id=order["id"],
        order_ref=order["name"],
        placed_at=order["processedAt"],
        fulfillment_status=order[
            "displayFulfillmentStatus"
        ],
        lines=[
            to_line(n, shipments)
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
