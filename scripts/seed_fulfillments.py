"""Ship and deliver lab orders so lines become returnable."""
import json, sys
from datetime import datetime, timedelta
sys.path.insert(0, "scripts")
from shopify_admin import gql

ORDERS = json.load(open("scripts/seed_orders.json"))
# order -> (skus to ship, event status, event time, tracking)
PLAN = {
    "SL-1042": (None, "DELIVERED", "2026-10-26T15:42:00Z", "1ZSL000001042"),
    "SL-1044": (["HDP-BT-R"], "IN_TRANSIT", "2026-10-29T07:10:00Z", "1ZSL000001044"),
    "SL-1045": (None, "DELIVERED", "2026-10-22T12:05:00Z", "1ZSL000001045"),
    "SL-1046": (None, "DELIVERED", "2026-10-28T11:30:00Z", "1ZSL000001046"),
}
FO = """query($id: ID!) { order(id: $id) {
  fulfillments(first: 5) { id }
  fulfillmentOrders(first: 5) { nodes { id status
    lineItems(first: 10) { nodes { id remainingQuantity sku } } } } } }"""
CREATE = """mutation($f: FulfillmentInput!) {
  fulfillmentCreate(fulfillment: $f) {
    fulfillment { id status } userErrors { field message } } }"""
EVENT = """mutation($e: FulfillmentEventInput!) {
  fulfillmentEventCreate(fulfillmentEvent: $e) {
    fulfillmentEvent { id status happenedAt } userErrors { field message } } }"""

for name, (skus, status, at, tracking) in PLAN.items():
    order = gql(FO, {"id": ORDERS[name]})["order"]
    if order["fulfillments"]:
        print(name, "already fulfilled"); continue
    groups = []
    for fo in order["fulfillmentOrders"]["nodes"]:
        items = [{"id": li["id"], "quantity": li["remainingQuantity"]}
                 for li in fo["lineItems"]["nodes"]
                 if li["remainingQuantity"] and (skus is None or li["sku"] in skus)]
        if items:
            groups.append({"fulfillmentOrderId": fo["id"], "fulfillmentOrderLineItems": items})
    d = gql(CREATE, {"f": {"lineItemsByFulfillmentOrder": groups, "notifyCustomer": False,
            "trackingInfo": {"company": "UPS", "number": tracking}}})["fulfillmentCreate"]
    if d["userErrors"]: raise SystemExit(name + json.dumps(d["userErrors"]))
    fid = d["fulfillment"]["id"]
    if status == "DELIVERED":
        gql(EVENT, {"e": {"fulfillmentId": fid, "status": "IN_TRANSIT", "happenedAt": (datetime.fromisoformat(at) - timedelta(days=1)).isoformat()}})
    e = gql(EVENT, {"e": {"fulfillmentId": fid, "status": status, "happenedAt": at}})["fulfillmentEventCreate"]
    if e["userErrors"]: raise SystemExit(name + json.dumps(e["userErrors"]))
    print(name, fid, e["fulfillmentEvent"])
