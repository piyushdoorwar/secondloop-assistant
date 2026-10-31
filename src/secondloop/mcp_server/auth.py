"""Token verification for the HTTP server."""

import os

from fastmcp.server.auth.providers.jwt import JWTVerifier

AUDIENCE = "secondloop-mcp"


def build_auth():
    """A JWT verifier, or None for local stdio runs."""
    jwks = os.environ.get("OIDC_JWKS_URI")
    key = os.environ.get("OIDC_PUBLIC_KEY")
    if not (jwks or key):
        return None
    return JWTVerifier(
        jwks_uri=jwks,
        public_key=key,
        issuer=os.environ["OIDC_ISSUER"],
        audience=AUDIENCE,
        algorithm="RS256",
        required_scopes=["support"],
    )
