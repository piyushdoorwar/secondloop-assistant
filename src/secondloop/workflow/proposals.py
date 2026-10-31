"""Exact, expiring proposals that a second person approves."""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.types.json import Jsonb

TTL = timedelta(hours=4)


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def canonical(spec: dict) -> str:
    return json.dumps(
        spec, sort_keys=True, separators=(",", ":")
    )


def digest(spec: dict) -> str:
    return hashlib.sha256(
        canonical(spec).encode()
    ).hexdigest()


def create(
    conn, kind, case, requester, spec, policy_version=None
) -> dict:
    now = datetime.now(timezone.utc)
    row = conn.execute(
        """
        INSERT INTO proposals
          (id, kind, case_id, store_id, requested_by,
           spec, spec_digest, policy_version,
           expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, spec_digest, expires_at
        """,
        (
            f"PRP-{uuid.uuid4().hex[:10]}",
            kind,
            case.case_id,
            case.store_id,
            requester,
            Jsonb(spec),
            digest(spec),
            policy_version,
            now + TTL,
        ),
    ).fetchone()
    conn.commit()
    return row


def decide(
    conn,
    proposal_id,
    approver,
    decision,
    seen_digest,
    installation,
) -> dict:
    """Record a decision; on approval, queue one operation."""
    try:
        return _decide(
            conn,
            proposal_id,
            approver,
            decision,
            seen_digest,
            installation,
        )
    except psycopg.errors.UniqueViolation:
        raise Refused("return_already_in_progress")


def _decide(
    conn,
    proposal_id,
    approver,
    decision,
    seen_digest,
    installation,
) -> dict:
    with conn.transaction():
        p = conn.execute(
            "SELECT * FROM proposals WHERE id = %s "
            "FOR UPDATE",
            (proposal_id,),
        ).fetchone()
        if p is None:
            raise Refused("proposal_not_found")
        if p["state"] != "pending":
            raise Refused("proposal_not_pending")
        if p["expires_at"] <= datetime.now(timezone.utc):
            raise Refused("proposal_expired")
        if "return_approve" not in approver.roles:
            raise Refused("approver_role_missing")
        if p["store_id"] not in approver.stores:
            raise Refused("approver_store_denied")
        if approver.subject == p["requested_by"]:
            raise Refused("second_person_required")
        if seen_digest != p["spec_digest"]:
            raise Refused("proposal_changed")
        conn.execute(
            "INSERT INTO approvals (proposal_id, "
            "decided_by, decision, spec_digest) "
            "VALUES (%s, %s, %s, %s)",
            (
                proposal_id,
                approver.subject,
                decision,
                seen_digest,
            ),
        )
        conn.execute(
            "UPDATE proposals SET state = %s "
            "WHERE id = %s",
            (decision, proposal_id),
        )
        if decision != "approved":
            return {
                "proposal_id": proposal_id,
                "state": decision,
            }
        op = conn.execute(
            """
            INSERT INTO operations
              (id, proposal_id, kind, case_id, spec,
               state, requested_by, approved_by,
               installation)
            VALUES (%s, %s, %s, %s, %s, 'ready',
                    %s, %s, %s)
            RETURNING id, state
            """,
            (
                f"OP-{uuid.uuid4().hex[:10]}",
                proposal_id,
                p["kind"],
                p["case_id"],
                Jsonb(p["spec"]),
                p["requested_by"],
                approver.subject,
                installation,
            ),
        ).fetchone()
    return {
        "proposal_id": proposal_id,
        "operation_id": op["id"],
        "state": op["state"],
    }
