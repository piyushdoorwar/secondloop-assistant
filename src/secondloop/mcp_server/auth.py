"""Token verification for the HTTP server."""

import os

from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier

AUDIENCE = "secondloop-mcp"


def build_auth():
    """A JWT verifier, or None for local stdio runs.

    With MCP_PUBLIC_URL set, the verifier is wrapped so the
    server also publishes OAuth protected resource metadata
    naming the identity provider (Appendix C).
    """
    jwks = os.environ.get("OIDC_JWKS_URI")
    key = os.environ.get("OIDC_PUBLIC_KEY")
    if not (jwks or key):
        return None
    verifier = JWTVerifier(
        jwks_uri=jwks,
        public_key=key,
        issuer=os.environ["OIDC_ISSUER"],
        audience=AUDIENCE,
        algorithm="RS256",
        required_scopes=["support"],
    )
    public_url = os.environ.get("MCP_PUBLIC_URL")
    if not public_url:
        return verifier
    return with_metadata(
        verifier, public_url, os.environ["OIDC_ISSUER"]
    )


def with_metadata(verifier, public_url, issuer):
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[issuer],
        base_url=public_url,
        scopes_supported=["support"],
        resource_name="SecondLoop support tools",
    )
