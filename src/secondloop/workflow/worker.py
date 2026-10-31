"""Carry out approved operations, once, with a record."""

import json
import uuid

from psycopg.types.json import Jsonb

from secondloop.telemetry import safe, tracer

CLAIM = """
UPDATE operations
SET state = 'submitting',
    attempts = attempts + 1,
    submitted_at = now(),
    lease_until = now() + interval '2 minutes',
    updated_at = now()
WHERE id = (
    SELECT id FROM operations
    WHERE state = 'ready'
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING *
"""


class Uncertain(Exception):
    """The request may or may not have taken effect."""


class Rejected(Exception):
    """The vendor refused; nothing was created."""


class TryLater(Exception):
    """Refused before any effect, e.g. throttled."""


def claim(conn):
    """Take one ready operation, or None."""
    row = conn.execute(CLAIM).fetchone()
    conn.commit()
    return row


def finish(
    conn,
    op_id,
    state,
    vendor_ref=None,
    detail=None,
    event=None,
):
    with conn.transaction():
        conn.execute(
            "UPDATE operations SET state = %s, "
            "vendor_ref = %s, detail = %s, "
            "lease_until = NULL, updated_at = now() "
            "WHERE id = %s",
            (state, vendor_ref, detail, op_id),
        )
        if event:
            conn.execute(
                "INSERT INTO outbox (id, operation_id, "
                "event_type, payload) "
                "VALUES (%s, %s, %s, %s)",
                (
                    f"EVT-{uuid.uuid4().hex[:10]}",
                    op_id,
                    event[0],
                    Jsonb(event[1]),
                ),
            )


def run_once(conn, vendors, checks) -> dict | None:
    """Claim, re-check, dispatch, record. One operation."""
    op = claim(conn)
    if op is None:
        return None
    with tracer.start_as_current_span(
        f"operation.{op['kind']}",
        attributes=safe(
            {
                "app.operation_id": op["id"],
                "app.case_id": op["case_id"],
            }
        ),
    ) as span:
        result = _dispatch(conn, op, vendors, checks)
        span.set_attributes(
            safe(
                {
                    "app.result": result["state"],
                    "app.code": result.get("detail"),
                }
            )
        )
        return result


def _dispatch(conn, op, vendors, checks) -> dict:
    problem = checks(op)
    if problem:
        finish(
            conn, op["id"], "needs_review", detail=problem
        )
        return {"id": op["id"], "state": "needs_review"}
    try:
        ref = vendors.dispatch(op)
    except TryLater as error:
        finish(conn, op["id"], "ready", detail=str(error))
        return {"id": op["id"], "state": "ready"}
    except Rejected as error:
        finish(
            conn, op["id"], "rejected", detail=str(error)
        )
        return {"id": op["id"], "state": "rejected"}
    except Uncertain as error:
        finish(
            conn, op["id"], "unknown", detail=str(error)
        )
        return {"id": op["id"], "state": "unknown"}
    event = None
    if op["kind"] == "return":
        event = (
            "return.confirmed",
            {
                "case_id": op["case_id"],
                "order_ref": op["spec"]["order_ref"],
                "return": ref,
            },
        )
    finish(
        conn,
        op["id"],
        "confirmed",
        vendor_ref=ref,
        event=event,
    )
    return {
        "id": op["id"],
        "state": "confirmed",
        "vendor_ref": ref,
    }
