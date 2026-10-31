"""Record live Admin API replies for the contract fake.

Run against your development store with SHOPIFY_MODE=live.
Writes one JSON file per operation and variables.
"""
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, "src")
from secondloop.cases import load_cases
from secondloop.shopify.factory import admin_client
from secondloop.shopify.orders import ORDER_BRIEF

OUT = pathlib.Path("data/shopify_recorded")


def record(client, operation, document, variables):
    data = client.query(document, variables)
    payload = {"data": data}
    key = json.dumps(variables, sort_keys=True)
    name = hashlib.sha256(key.encode()).hexdigest()[:10]
    path = OUT / f"{operation}-{name}.json"
    path.write_text(json.dumps({
        "operation": operation,
        "variables": variables,
        "response": payload,
    }, indent=2) + "\n")
    return path


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for case in load_cases().values():
        client = admin_client(case.shop)
        path = record(client, "OrderBrief", ORDER_BRIEF,
                      {"id": case.order_id})
        print(case.case_id, "->", path.name)
