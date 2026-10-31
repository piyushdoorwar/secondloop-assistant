"""Check each account the project uses, and say what is wrong.

python scripts/check_setup.py
Reads only. Posts nothing, creates nothing.
"""

import os

import httpx2 as httpx
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from scripts.shopify_admin import gql


def check(name, fn):
    try:
        print(f"ok    {name}: {fn()}")
    except Exception as exc:  # report, keep going
        print(f"FAIL  {name}: {str(exc)[:300]}")


def shopify_token():
    shop = os.environ["SHOPIFY_SHOP"]
    r = httpx.post(
        f"https://{shop}/admin/oauth/access_token",
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["SHOPIFY_CLIENT_ID"],
            "client_secret": os.environ[
                "SHOPIFY_CLIENT_SECRET"
            ],
        },
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return f"expires_in={r.json()['expires_in']}"


def shopify_scopes():
    data = gql(
        "{ currentAppInstallation"
        " { accessScopes { handle } } }"
    )
    scopes = data["currentAppInstallation"]["accessScopes"]
    return ", ".join(sorted(s["handle"] for s in scopes))


def shopify_orders():
    data = gql("{ orders(first: 1) { nodes { name } } }")
    return data["orders"]["nodes"][0]["name"]


def slack():
    token = os.environ["SLACK_BOT_TOKEN"]
    if not token.startswith("xoxb-"):
        raise RuntimeError(
            "SLACK_BOT_TOKEN is not a bot token (xoxb-)"
        )
    client = WebClient(token=token, timeout=10)
    who = client.auth_test()
    channel = os.environ["SLACK_OPERATIONS_CHANNEL"]
    try:
        client.conversations_history(
            channel=channel, limit=1
        )
    except SlackApiError as exc:
        raise RuntimeError(
            f"{channel}: {exc.response['error']}"
        ) from None
    return f"bot {who['user']} can read {channel}"


def anthropic():
    import anthropic as sdk

    model = os.environ.get(
        "CLAUDE_MODEL", "claude-sonnet-5-5"
    )
    sdk.Anthropic().models.retrieve(model)
    return f"{model} available"


if __name__ == "__main__":
    check("shopify token", shopify_token)
    check("shopify scopes", shopify_scopes)
    check("shopify orders", shopify_orders)
    check("slack", slack)
    check("anthropic", anthropic)
