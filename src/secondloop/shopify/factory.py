"""Build one Admin client per shop and mode."""

from functools import lru_cache

import httpx2 as httpx

from secondloop.config import shopify_settings
from secondloop.shopify.client import (
    AdminClient,
    ClientCredentials,
    admin_endpoint,
)
from secondloop.shopify.fake import fake_transport


def admin_client(shop: str) -> AdminClient:
    return _client(shop, shopify_settings())


@lru_cache(maxsize=16)
def _client(shop, settings) -> AdminClient:
    if settings.mode == "live":
        http = httpx.Client(
            timeout=10.0, follow_redirects=False
        )
    else:
        http = httpx.Client(transport=fake_transport())
    tokens = ClientCredentials(
        shop,
        settings.client_id or "fake",
        settings.client_secret or "fake",
        http,
    )
    endpoint = admin_endpoint(shop, settings.api_version)
    return AdminClient(endpoint, tokens, http)
