"""Chapter 9 end to end against the lab store and Slack.

Mira proposes, Leena approves in the console API, the
worker runs once. Needs SHOPIFY_MODE=live, Slack and a
database. Creates a real return in the dev store.
"""

import asyncio
import json
import os
import sys

from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.server.auth.providers.jwt import RSAKeyPair

KEYS = RSAKeyPair.generate()
os.environ.update(
    {
        "SECONDLOOP_ENV": "dev",
        "SECONDLOOP_DEV_SUBJECT": "mira",
        "CONSOLE_PUBLIC_KEY": KEYS.public_key,
        "OIDC_ISSUER": "https://idp.secondloop.test",
    }
)

from secondloop.console.app import app  # noqa: E402
from secondloop.mcp_server.server import mcp  # noqa
from secondloop.workflow.db import (
    connect,
    migrate,
)  # noqa
from secondloop.workflow.run import main as work  # noqa


def leena():
    token = KEYS.create_token(
        subject="leena",
        issuer="https://idp.secondloop.test",
        audience="secondloop-console",
        additional_claims={
            "stores": ["secondloop-lab"],
            "roles": ["return_approve"],
        },
    )
    return {"Authorization": f"Bearer {token}"}


async def propose(tool, args):
    async with Client(mcp) as client:
        result = await client.call_tool(tool, args)
    print(tool, json.dumps(result.data, indent=1))
    return result.data["proposal_id"]


def approve(console, pid):
    shown = console.get(
        f"/proposals/{pid}", headers=leena()
    ).json()
    decided = console.post(
        f"/proposals/{pid}/decision",
        json={
            "decision": "approved",
            "spec_digest": shown["spec_digest"],
        },
        headers=leena(),
    ).json()
    print("decision", decided)


if __name__ == "__main__":
    with connect() as conn:
        migrate(conn)
    console = TestClient(app)
    kind = sys.argv[1]
    if kind == "return":
        pid = asyncio.run(
            propose(
                "propose_return",
                {"case_id": "CASE-17", "sku": "LAP-14-R"},
            )
        )
    else:
        pid = asyncio.run(
            propose(
                "propose_escalation",
                {
                    "case_id": "CASE-17",
                    "summary": sys.argv[2],
                },
            )
        )
    approve(console, pid)
    work(once=True)
