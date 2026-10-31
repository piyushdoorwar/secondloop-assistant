"""Who is asking, and what may they do?"""

import json
import os
from dataclasses import dataclass

from fastmcp.server.dependencies import get_access_token

from secondloop.cases import DATA


@dataclass(frozen=True)
class Principal:
    subject: str
    stores: frozenset[str]
    roles: frozenset[str]


class Denied(Exception):
    """The caller may not do this."""


def principal_from_claims(claims: dict) -> Principal:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise Denied("subject_missing")
    lists = {}
    for key in ("stores", "roles"):
        value = claims.get(key)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise Denied(f"{key}_claim_invalid")
        lists[key] = frozenset(value)
    return Principal(
        subject, lists["stores"], lists["roles"]
    )


def dev_principal() -> Principal | None:
    """Local stdio runs only: a fixed employee."""
    if os.environ.get("SECONDLOOP_ENV") != "dev":
        return None
    subject = os.environ.get("SECONDLOOP_DEV_SUBJECT")
    rows = json.loads(
        (DATA / "employees.json").read_text()
    )
    for row in rows:
        if row["sub"] == subject:
            return principal_from_claims(row)
    return None


def current_principal() -> Principal:
    token = get_access_token()
    if token is not None:
        return principal_from_claims(token.claims)
    principal = dev_principal()
    if principal is None:
        raise Denied("authentication_required")
    return principal


def authorize_case(principal, case, role="support_read"):
    if role not in principal.roles:
        raise Denied("role_missing")
    if case.store_id not in principal.stores:
        raise Denied("store_not_permitted")
