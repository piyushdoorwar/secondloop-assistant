"""Identity over the real HTTP transport."""

import socket
import threading
import time

import httpx2 as httpx
import pytest
import uvicorn
from fastmcp import Client
from fastmcp.server.auth.providers.jwt import (
    JWTVerifier,
    RSAKeyPair,
)

from secondloop.mcp_server.server import mcp

pytestmark = pytest.mark.anyio
ISSUER = "https://idp.secondloop.test"
KEYS = RSAKeyPair.generate()


def token(sub, stores, roles, audience="secondloop-mcp"):
    return KEYS.create_token(
        subject=sub,
        issuer=ISSUER,
        audience=audience,
        scopes=["support"],
        additional_claims={
            "stores": stores,
            "roles": roles,
        },
    )


@pytest.fixture(scope="module")
def url():
    mcp.auth = JWTVerifier(
        public_key=KEYS.public_key,
        issuer=ISSUER,
        audience="secondloop-mcp",
        algorithm="RS256",
        required_scopes=["support"],
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(
        mcp.http_app(), port=port, log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run, daemon=True
    )
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join(5)
    mcp.auth = None


async def brief(url, bearer):
    async with Client(url, auth=bearer) as client:
        result = await client.call_tool(
            "get_order_brief", {"case_id": "CASE-17"}
        )
    return result.data


async def test_store_employee_can_read(url, monkeypatch):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    monkeypatch.delenv("SECONDLOOP_ENV")
    data = await brief(
        url,
        token(
            "ben", ["secondloop-lab"], ["support_read"]
        ),
    )
    assert data["brief"]["order_ref"] == "SL-1042"


async def test_other_store_sees_no_such_case(
    url, monkeypatch
):
    monkeypatch.delenv("SECONDLOOP_ENV")
    data = await brief(
        url,
        token("ana", ["northwind-dev"], ["support_read"]),
    )
    assert data["code"] == "case_not_found"


def discover(url, bearer=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "server/discover",
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            }
        },
    }
    return httpx.post(url, json=body, headers=headers)


def test_wrong_audience_never_reaches_a_tool(url):
    bad = token(
        "ben",
        ["secondloop-lab"],
        ["support_read"],
        audience="shopify",
    )
    response = discover(url, bad)
    assert response.status_code == 401


def test_no_token_is_refused(url):
    response = discover(url)
    assert response.status_code == 401
    assert (
        "Bearer" in response.headers["www-authenticate"]
    )
