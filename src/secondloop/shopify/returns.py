"""Return lines, reasons, and the approved return write."""

from pydantic import BaseModel

RETURNABLE_LINES = """
query ReturnableLines($id: ID!) {
  returnableFulfillments(orderId: $id, first: 5) {
    nodes {
      returnableFulfillmentLineItems(first: 10) {
        nodes {
          quantity
          fulfillmentLineItem {
            id
            lineItem { sku }
          }
        }
        pageInfo { hasNextPage }
      }
    }
    pageInfo { hasNextPage }
  }
}
"""

DAMAGE_REASON = """
query DamageReason {
  returnReasonDefinitions(
    first: 1, query: "handle:damaged-or-defective"
  ) {
    nodes { id handle }
  }
}
"""

CREATE_RETURN = """
mutation CreateReturn($input: ReturnInput!) {
  returnCreate(returnInput: $input) {
    return { id name status }
    userErrors { field message }
  }
}
"""

ORDER_RETURNS = """
query OrderReturns($id: ID!) {
  order(id: $id) {
    returns(first: 10) {
      nodes {
        id
        name
        status
        returnLineItems(first: 10) {
          nodes {
            quantity
            ... on ReturnLineItem {
              fulfillmentLineItem { id }
            }
          }
        }
      }
    }
  }
}
"""


class ReturnableLine(BaseModel):
    fulfillment_line_item_id: str
    sku: str | None
    quantity: int


class Incomplete(Exception):
    """A page limit was reached; the list is partial."""


def returnable_lines(client, order_id):
    data = client.query(
        RETURNABLE_LINES, {"id": order_id}
    )
    outer = data["returnableFulfillments"]
    if outer["pageInfo"]["hasNextPage"]:
        raise Incomplete("returnable_fulfillments")
    lines = []
    for node in outer["nodes"]:
        inner = node["returnableFulfillmentLineItems"]
        if inner["pageInfo"]["hasNextPage"]:
            raise Incomplete("returnable_line_items")
        for item in inner["nodes"]:
            fli = item["fulfillmentLineItem"]
            lines.append(
                ReturnableLine(
                    fulfillment_line_item_id=fli["id"],
                    sku=fli["lineItem"]["sku"],
                    quantity=item["quantity"],
                )
            )
    return lines


def damage_reason_id(client) -> str:
    data = client.query(DAMAGE_REASON, {})
    return data["returnReasonDefinitions"]["nodes"][0][
        "id"
    ]


def create_return(client, spec) -> dict:
    """Send one approved return. No retries here."""
    data = client.query(
        CREATE_RETURN,
        {
            "input": {
                "orderId": spec["order_id"],
                "returnLineItems": [
                    {
                        "fulfillmentLineItemId": spec[
                            "fulfillment_line_item_id"
                        ],
                        "quantity": spec["quantity"],
                        "returnReasonDefinitionId": spec[
                            "reason_definition_id"
                        ],
                    }
                ],
            }
        },
    )
    return data["returnCreate"]


def order_returns(client, order_id) -> list[dict]:
    data = client.query(ORDER_RETURNS, {"id": order_id})
    return data["order"]["returns"]["nodes"]
