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
                "sku": "LAP-14-R",
                "quantity": 1,
                "currentQuantity": 1,
            },
        ]
    },
    "fulfillments": [
        {
            "displayStatus": "IN_TRANSIT",
            "deliveredAt": None,
        },
    ],
    "returns": {"nodes": []},
}


def test_in_transit_is_not_delivered():
    brief = to_brief(ORDER)
    assert (
        brief.fulfillment_status == "PARTIALLY_FULFILLED"
    )
    assert brief.delivered_at is None


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
