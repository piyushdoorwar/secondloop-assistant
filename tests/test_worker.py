import json

import pytest
from psycopg.types.json import Jsonb

from secondloop.workflow import worker
from secondloop.workflow.db import connect
from conftest import TEST_DB


def queue(db, case_id="CASE-17", kind="return"):
    db.execute(
        "INSERT INTO proposals (id, kind, case_id, "
        "store_id, requested_by, spec, spec_digest, "
        "expires_at, state) VALUES (%s, %s, %s, "
        "'secondloop-lab', 'mira', %s, 'd', "
        "now() + interval '1 hour', 'approved')",
        (
            f"PRP-{case_id}",
            kind,
            case_id,
            Jsonb({"order_ref": "SL-1042"}),
        ),
    )
    db.execute(
        "INSERT INTO operations (id, proposal_id, kind, "
        "case_id, spec, state, requested_by, "
        "approved_by, installation) VALUES (%s, %s, %s, "
        "%s, %s, 'ready', 'mira', 'leena', 'lab')",
        (
            f"OP-{case_id}",
            f"PRP-{case_id}",
            kind,
            case_id,
            Jsonb({"order_ref": "SL-1042"}),
        ),
    )
    db.commit()


class Vendors:
    """Records sends; can lose the response."""

    def __init__(self, outcome="ok"):
        self.outcome = outcome
        self.sent = []

    def dispatch(self, op):
        self.sent.append(op["id"])
        if self.outcome == "lost":
            raise worker.Uncertain("ReadTimeout")
        if self.outcome == "refused":
            raise worker.Rejected("Quantity unavailable")
        return "SL-1042-R1"


def state(db, op_id="OP-CASE-17"):
    return db.execute(
        "SELECT state, vendor_ref FROM operations "
        "WHERE id = %s",
        (op_id,),
    ).fetchone()


def test_confirmed_return_writes_outbox_event(db):
    queue(db)
    worker.run_once(db, Vendors(), lambda op: None)
    assert state(db) == {
        "state": "confirmed",
        "vendor_ref": "SL-1042-R1",
    }
    event = db.execute("SELECT * FROM outbox").fetchone()
    assert event["event_type"] == "return.confirmed"


def test_lost_response_is_unknown_and_not_resent(db):
    queue(db)
    vendors = Vendors("lost")
    worker.run_once(db, vendors, lambda op: None)
    again = worker.run_once(db, vendors, lambda op: None)
    assert state(db)["state"] == "unknown"
    assert again is None
    assert vendors.sent == ["OP-CASE-17"]


def test_failed_recheck_sends_nothing(db):
    queue(db)
    vendors = Vendors()
    worker.run_once(
        db, vendors, lambda op: "policy_changed"
    )
    assert state(db)["state"] == "needs_review"
    assert vendors.sent == []


def test_two_workers_never_share_an_operation(db):
    queue(db, "CASE-17")
    queue(db, "CASE-18")
    a, b = connect(TEST_DB), connect(TEST_DB)
    try:
        with a.transaction(), b.transaction():
            first = a.execute(worker.CLAIM).fetchone()
            second = b.execute(worker.CLAIM).fetchone()
            third = b.execute(worker.CLAIM).fetchone()
    finally:
        a.close()
        b.close()
    assert {first["id"], second["id"]} == {
        "OP-CASE-17",
        "OP-CASE-18",
    }
    assert third is None
