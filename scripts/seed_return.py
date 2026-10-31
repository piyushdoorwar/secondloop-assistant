"""Open the existing return on SL-1045 (Priya Nair)."""

import json, sys

sys.path.insert(0, "scripts")
from shopify_admin import gql

ORDERS = json.load(open("scripts/seed_orders.json"))
oid = ORDERS["SL-1045"]
have = gql(
    "query($id:ID!){order(id:$id){returns(first:5){nodes{id status}}}}",
    {"id": oid},
)
if have["order"]["returns"]["nodes"]:
    print("exists", have)
    raise SystemExit
lines = gql(
    """query($id:ID!){ returnableFulfillments(orderId:$id, first:5){ nodes{
  returnableFulfillmentLineItems(first:10){ nodes{ quantity fulfillmentLineItem{ id } } } } } }""",
    {"id": oid},
)["returnableFulfillments"]["nodes"][0][
    "returnableFulfillmentLineItems"
][
    "nodes"
]
M = """mutation CreateReturn($input: ReturnInput!) {
  returnCreate(returnInput: $input) { return { id status name } userErrors { field message } } }"""
d = gql(
    M,
    {
        "input": {
            "orderId": oid,
            "returnLineItems": [
                {
                    "fulfillmentLineItemId": lines[0][
                        "fulfillmentLineItem"
                    ]["id"],
                    "quantity": 1,
                    "returnReasonDefinitionId": "gid://shopify/ReturnReasonDefinition/2",
                }
            ],
        }
    },
)
print(json.dumps(d, indent=1))
