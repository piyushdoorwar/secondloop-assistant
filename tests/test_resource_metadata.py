"""Protected resource metadata (Appendix C)."""

from fastmcp.server.auth.providers.jwt import (
    JWTVerifier,
    RSAKeyPair,
)
from starlette.testclient import TestClient

from secondloop.mcp_server.auth import with_metadata
from secondloop.mcp_server.server import mcp

ISSUER = "https://idp.secondloop.test"
PUBLIC = "https://mcp.secondloop.test"


def test_metadata_names_the_identity_provider():
    keys = RSAKeyPair.generate()
    verifier = JWTVerifier(
        public_key=keys.public_key,
        issuer=ISSUER,
        audience="secondloop-mcp",
        algorithm="RS256",
        required_scopes=["support"],
    )
    mcp.auth = with_metadata(verifier, PUBLIC, ISSUER)
    try:
        app = mcp.http_app()
        with TestClient(app, base_url=PUBLIC) as client:
            denied = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1,
                      "method": "server/discover"},
                headers={"Accept": "application/json, "
                         "text/event-stream"},
            )
            challenge = denied.headers["www-authenticate"]
            meta = client.get(
                "/.well-known/oauth-protected-resource/mcp"
            )
    finally:
        mcp.auth = None
    print(denied.status_code, challenge)
    print(meta.json())
    assert denied.status_code == 401
    assert "resource_metadata=" in challenge
    body = meta.json()
    assert body["authorization_servers"] == [ISSUER]
    assert body["scopes_supported"] == ["support"]
