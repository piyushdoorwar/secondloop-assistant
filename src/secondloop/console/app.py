"""The support console's approval endpoints.

The model never calls these. A person signs in to the
console, reads the stored proposal, and decides.
"""

import os
from typing import Literal

import jwt
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
)
from pydantic import BaseModel

from secondloop.identity import (
    Denied,
    principal_from_claims,
)
from secondloop.workflow import proposals
from secondloop.workflow.db import connect

app = FastAPI(title="SecondLoop console API")
AUDIENCE = "secondloop-console"
INSTALLATION = "secondloop-lab/SecondLoop Assistant"


def signing_key(raw: str):
    jwks = os.environ.get("OIDC_JWKS_URI")
    if jwks:
        return (
            jwt.PyJWKClient(jwks)
            .get_signing_key_from_jwt(raw)
            .key
        )
    return os.environ["CONSOLE_PUBLIC_KEY"]


def approver(authorization: str = Header()):
    scheme, _, raw = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(401)
    try:
        claims = jwt.decode(
            raw,
            signing_key(raw),
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=os.environ["OIDC_ISSUER"],
        )
        return principal_from_claims(claims)
    except (jwt.PyJWTError, Denied):
        raise HTTPException(401)


class Decision(BaseModel):
    decision: Literal["approved", "rejected"]
    spec_digest: str


@app.get("/proposals/{proposal_id}")
def show(proposal_id: str, who=Depends(approver)):
    """What the approval screen renders."""
    with connect() as conn:
        p = conn.execute(
            "SELECT id, kind, case_id, store_id, "
            "requested_by, spec, spec_digest, "
            "policy_version, state, expires_at "
            "FROM proposals WHERE id = %s",
            (proposal_id,),
        ).fetchone()
    if p is None or p["store_id"] not in who.stores:
        raise HTTPException(404)
    return p


@app.post("/proposals/{proposal_id}/decision")
def decide(
    proposal_id: str,
    body: Decision,
    who=Depends(approver),
):
    with connect() as conn:
        try:
            return proposals.decide(
                conn,
                proposal_id,
                who,
                body.decision,
                body.spec_digest,
                INSTALLATION,
            )
        except proposals.Refused as refused:
            raise HTTPException(409, refused.code)
