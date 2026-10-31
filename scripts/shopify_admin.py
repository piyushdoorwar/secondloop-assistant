"""Small Admin GraphQL helper for lab scripts (client-credentials token, cached 23h)."""
import json, os, time, pathlib
import httpx2 as httpx

API_VERSION = "2026-10"
CACHE = pathlib.Path(os.path.expanduser("~/.secrets/shopify_token.json"))

def _token() -> str:
    if CACHE.exists():
        d = json.loads(CACHE.read_text())
        if d["expires_at"] > time.time() + 300:
            return d["access_token"]
    shop = os.environ["SHOPIFY_SHOP"]
    r = httpx.post(f"https://{shop}/admin/oauth/access_token", data={
        "grant_type": "client_credentials",
        "client_id": os.environ["SHOPIFY_CLIENT_ID"],
        "client_secret": os.environ["SHOPIFY_CLIENT_SECRET"]}, timeout=20)
    r.raise_for_status()
    d = r.json()
    CACHE.write_text(json.dumps({"access_token": d["access_token"],
                                 "expires_at": time.time() + d["expires_in"]}))
    CACHE.chmod(0o600)
    return d["access_token"]

def gql(query: str, variables: dict | None = None) -> dict:
    shop = os.environ["SHOPIFY_SHOP"]
    r = httpx.post(f"https://{shop}/admin/api/{API_VERSION}/graphql.json",
                   json={"query": query, "variables": variables or {}},
                   headers={"X-Shopify-Access-Token": _token()}, timeout=30)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(json.dumps(body["errors"])[:800])
    return body["data"]
