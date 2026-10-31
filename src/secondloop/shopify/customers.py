"""List a customer's recent orders as candidates."""

from pydantic import BaseModel

CANDIDATE_ORDERS = """
query CandidateOrders(
  $id: ID!, $first: Int!, $after: String
) {
  customer(id: $id) {
    orders(
      first: $first, after: $after,
      sortKey: PROCESSED_AT, reverse: true
    ) {
      nodes {
        id
        name
        processedAt
        displayFulfillmentStatus
        lineItems(first: 5) { nodes { sku } }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


class Candidate(BaseModel):
    order_ref: str
    placed_at: str
    fulfillment_status: str
    skus: list[str]


class CandidatePage(BaseModel):
    candidates: list[Candidate]
    has_more: bool
    vendor_cursor: str | None


def read_candidates(
    client, customer_id, first=3, after=None
):
    data = client.query(
        CANDIDATE_ORDERS,
        {
            "id": customer_id,
            "first": first,
            "after": after,
        },
    )
    customer = data.get("customer")
    if customer is None:
        return None
    orders = customer["orders"]
    return CandidatePage(
        candidates=[
            Candidate(
                order_ref=n["name"],
                placed_at=n["processedAt"],
                fulfillment_status=n[
                    "displayFulfillmentStatus"
                ],
                skus=[
                    li["sku"]
                    for li in n["lineItems"]["nodes"]
                    if li["sku"]
                ],
            )
            for n in orders["nodes"]
        ],
        has_more=orders["pageInfo"]["hasNextPage"],
        vendor_cursor=orders["pageInfo"]["endCursor"],
    )
