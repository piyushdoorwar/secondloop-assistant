"""A small Shopify Admin GraphQL client."""

import re
import time

import httpx2 as httpx

SHOP_PATTERN = r"[a-z0-9][a-z0-9-]*\.myshopify\.com"


class ShopifyError(Exception):
    """A failure with a stable, loggable code."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail


def check_shop(shop: str) -> str:
    if not re.fullmatch(SHOP_PATTERN, shop):
        raise ShopifyError("invalid_shop_domain")
    return shop


class ClientCredentials:
    """Exchange app credentials for a 24-hour token."""

    def __init__(
        self,
        shop,
        client_id,
        client_secret,
        http: httpx.Client,
    ):
        self.url = (
            f"https://{check_shop(shop)}"
            "/admin/oauth/access_token"
        )
        self.form = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        self.http = http
        self._token = None
        self._expires_at = 0.0

    def token(self) -> str:
        if time.time() < self._expires_at - 300:
            return self._token
        response = self.http.post(
            self.url, data=self.form
        )
        if response.status_code != 200:
            raise ShopifyError(
                "token_exchange_failed",
                str(response.status_code),
            )
        body = response.json()
        self._token = body["access_token"]
        self._expires_at = (
            time.time() + body["expires_in"]
        )
        return self._token


class AdminClient:
    def __init__(
        self,
        endpoint: str,
        token_source,
        http: httpx.Client,
    ):
        self.endpoint = endpoint
        self.token_source = token_source
        self.http = http
        self.last_cost = None

    def query(
        self, document: str, variables: dict
    ) -> dict:
        response = self.http.post(
            self.endpoint,
            headers={
                "X-Shopify-Access-Token": (
                    self.token_source.token()
                )
            },
            json={
                "query": document,
                "variables": variables,
            },
        )
        if response.status_code in (401, 403):
            raise ShopifyError("not_authorized")
        if response.status_code == 429:
            raise ShopifyError("throttled")
        response.raise_for_status()
        return self._unwrap(response.json())

    def _unwrap(self, payload: dict) -> dict:
        self.last_cost = payload.get(
            "extensions", {}
        ).get("cost")
        for error in payload.get("errors", []):
            code = error.get("extensions", {}).get("code")
            if code == "ACCESS_DENIED":
                raise ShopifyError(
                    "access_denied",
                    error.get("message", ""),
                )
            if code == "THROTTLED":
                raise ShopifyError("throttled")
            raise ShopifyError(
                "graphql_error", error.get("message", "")
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ShopifyError("missing_data")
        return data


def admin_endpoint(shop: str, version: str) -> str:
    return (
        f"https://{check_shop(shop)}"
        f"/admin/api/{version}/graphql.json"
    )
