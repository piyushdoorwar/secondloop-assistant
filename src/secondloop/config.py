"""Settings read once from the environment."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ShopifySettings:
    mode: str
    shop: str
    client_id: str
    client_secret: str
    api_version: str = "2026-10"


def shopify_settings() -> ShopifySettings:
    return ShopifySettings(
        mode=os.environ.get("SHOPIFY_MODE", "fake"),
        shop=os.environ.get("SHOPIFY_SHOP", ""),
        client_id=os.environ.get("SHOPIFY_CLIENT_ID", ""),
        client_secret=os.environ.get(
            "SHOPIFY_CLIENT_SECRET", ""
        ),
    )
