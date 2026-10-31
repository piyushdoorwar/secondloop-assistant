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
from secondloop.shopify.customers import CANDIDATE_ORDERS
from secondloop.shopify.orders import ORDER_BRIEF
from secondloop.shopify.returns import (
    DAMAGE_REASON,
    RETURNABLE_LINES,
)
from secondloop.shopify.shop import SHOP_TIMEZONE

OUT = pathlib.Path("data/shopify_recorded")


def record(client, operation, document, variables):
    data = client.query(document, variables)
    payload = {"data": data}
    key = json.dumps(variables, sort_keys=True)
    name = hashlib.sha256(key.encode()).hexdigest()[:10]
    path = OUT / f"{operation}-{name}.json"
    if path.exists() and json.loads(path.read_text()).get(
        "pinned"
    ):
        return path
    path.write_text(
        json.dumps(
            {
                "operation": operation,
                "variables": variables,
                "response": payload,
            },
            indent=2,
        )
        + "\n"
    )
    return path


def record_candidates(client, case):
    after = None
    for size in (3, 1, 1):
        variables = {
            "id": case.customer_id,
            "first": size,
            "after": after,
        }
        path = record(
            client,
            "CandidateOrders",
            CANDIDATE_ORDERS,
            variables,
        )
        print(case.case_id, "->", path.name)
        if size == 1:
            saved = json.loads(path.read_text())
            orders = saved["response"]["data"][
                "customer"
            ]["orders"]
            after = orders["pageInfo"]["endCursor"]


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    shops = set()
    for case in load_cases().values():
        client = admin_client(case.shop)
        if case.shop not in shops:
            shops.add(case.shop)
            for name, doc in (
                ("ShopTimezone", SHOP_TIMEZONE),
                ("DamageReason", DAMAGE_REASON),
            ):
                path = record(client, name, doc, {})
                print(case.shop, "->", path.name)
        if case.order_id:
            path = record(
                client,
                "OrderBrief",
                ORDER_BRIEF,
                {"id": case.order_id},
            )
            print(case.case_id, "->", path.name)
            path = record(
                client,
                "ReturnableLines",
                RETURNABLE_LINES,
                {"id": case.order_id},
            )
            print(case.case_id, "->", path.name)
        if case.customer_id:
            record_candidates(client, case)
