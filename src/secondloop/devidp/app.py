"""A development identity provider. Never deploy it.

Issues RS256 tokens for the lab employees and publishes
its public key as a JWKS document. A real deployment uses
the organisation's own OIDC provider instead.
"""

import json
import os
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException
from jwt.algorithms import RSAAlgorithm
from pydantic import BaseModel

from secondloop.cases import DATA

ISSUER = os.environ.get("OIDC_ISSUER", "http://idp:8000")
KEY = rsa.generate_private_key(
    public_exponent=65537, key_size=2048
)
KID = "lab-1"
app = FastAPI(title="SecondLoop dev identity provider")


class TokenRequest(BaseModel):
    subject: str
    audience: str


@app.get("/.well-known/jwks.json")
def jwks():
    public = json.loads(
        RSAAlgorithm.to_jwk(KEY.public_key())
    )
    return {
        "keys": [
            {
                **public,
                "kid": KID,
                "use": "sig",
                "alg": "RS256",
            }
        ]
    }


@app.get("/public-key.pem")
def public_key():
    pem = KEY.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return {"pem": pem.decode()}


@app.post("/token")
def token(body: TokenRequest):
    rows = json.loads(
        (DATA / "employees.json").read_text()
    )
    who = next(
        (r for r in rows if r["sub"] == body.subject),
        None,
    )
    if who is None:
        raise HTTPException(404, "unknown employee")
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": who["sub"],
        "aud": body.audience,
        "iat": now,
        "exp": now + 900,
        "scope": "support",
        "stores": who["stores"],
        "roles": who["roles"],
    }
    raw = jwt.encode(
        claims,
        KEY,
        algorithm="RS256",
        headers={"kid": KID},
    )
    return {"access_token": raw, "expires_in": 900}
