import json

import pytest

from secondloop.shopify.client import (
    AdminClient,
    ShopifyError,
)
from secondloop.shopify.orders import to_brief

ORDER = {
    "id": "gid://shopify/Order/1",
    "name": "SL-1044",
    "processedAt": "2026-10-22T14:05:00Z",
    "displayFulfillmentStatus": "PARTIALLY_FULFILLED",
    "lineItems": {
        "nodes": [
            {
                "id": "L1",
                "sku": "LAP-14-R",
                "quantity": 1,
                "currentQuantity": 1,
                "unfulfilledQuantity": 1,
            },
            {
                "id": "L2",
                "sku": "HDP-BT-R",
                "quantity": 1,
                "currentQuantity": 1,
                "unfulfilledQuantity": 0,
            },
        ]
    },
    "fulfillments": [
        {
            "displayStatus": "IN_TRANSIT",
            "deliveredAt": None,
            "fulfillmentLineItems": {
                "nodes": [
                    {"lineItem": {"id": "L2"}},
                ]
            },
        }
    ],
    "returns": {"nodes": []},
}


def test_lines_carry_their_own_shipment():
    laptop, phones = to_brief(ORDER).lines
    assert laptop.shipment == "NOT_SHIPPED"
    assert laptop.unshipped == 1
    assert phones.shipment == "IN_TRANSIT"
    assert phones.delivered_at is None


def test_access_denied_is_its_own_error():
    # Message recorded from the lab store before
    # protected customer data access was granted.
    payload = {
        "errors": [
            {
                "message": "This app is not approved to "
                "access the Order object.",
                "extensions": {"code": "ACCESS_DENIED"},
            }
        ]
    }
    client = AdminClient("unused", None, None)
    with pytest.raises(ShopifyError) as caught:
        client._unwrap(payload)
    assert caught.value.code == "access_denied"
