import pytest
from psycopg.types.json import Jsonb

from secondloop.shopify.factory import admin_client
from secondloop.workflow import outbox, reconcile

LAPTOP_LINE = (
    "gid://shopify/FulfillmentLineItem/10076217999567"
)
SPEC = {
    "order_id": "gid://shopify/Order/4934721994959",
    "order_ref": "SL-1042",
    "fulfillment_line_item_id": LAPTOP_LINE,
    "quantity": 1,
}


def unknown_return(db, spec=SPEC):
    db.execute(
        "INSERT INTO proposals (id, kind, case_id, "
        "store_id, requested_by, spec, spec_digest, "
        "expires_at, state) VALUES ('PRP-1', 'return', "
        "'CASE-17', 'secondloop-lab', 'mira', %s, 'd', "
        "now(), 'approved')",
        (Jsonb(spec),),
    )
    db.execute(
        "INSERT INTO operations (id, proposal_id, kind, "
        "case_id, spec, state, requested_by, approved_by, "
        "installation, submitted_at) VALUES ('OP-1', "
        "'PRP-1', 'return', 'CASE-17', %s, 'unknown', "
        "'mira', 'leena', 'lab', now())",
        (Jsonb(spec),),
    )
    db.commit()


def test_lost_return_is_found_in_shopify(db, monkeypatch):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    unknown_return(db)
    [result] = reconcile.reconcile(db)
    assert result["state"] == "confirmed"
    assert result["vendor_ref"] == "SL-1042-R1"


def test_no_evidence_means_review_not_retry(
    db, monkeypatch
):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    unknown_return(db, {**SPEC, "quantity": 2})
    [result] = reconcile.reconcile(db)
    assert result["state"] == "needs_review"


def test_vanished_worker_leaves_unknown(db):
    unknown_return(db)
    db.execute(
        "UPDATE operations SET state = "
        "'submitting', lease_until = now() - "
        "interval '1 minute'"
    )
    db.commit()
    assert reconcile.expire_leases(db) == ["OP-1"]


class FlakySlack:
    """Accepts the first post, then loses the reply."""

    def __init__(self):
        self.messages = []

    def chat_postMessage(self, **kw):
        self.messages.append(
            {
                "ts": f"{len(self.messages)}.0",
                "metadata": kw["metadata"],
            }
        )
        if len(self.messages) == 1:
            raise TimeoutError("reply lost")
        return {"ts": self.messages[-1]["ts"]}

    def conversations_history(self, **kw):
        return {"messages": self.messages}


def test_outbox_retry_checks_before_posting(db):
    unknown_return(db)
    db.execute(
        "INSERT INTO outbox (id, operation_id, "
        "event_type, payload) VALUES ('EVT-1', 'OP-1', "
        "'return.confirmed', %s)",
        (
            Jsonb(
                {
                    "case_id": "CASE-17",
                    "return": "SL-1042-R1",
                    "order_ref": "SL-1042",
                }
            ),
        ),
    )
    db.commit()
    client = FlakySlack()
    first = outbox.deliver_one(db, client, "C-OPS")
    second = outbox.deliver_one(db, client, "C-OPS")
    assert first["state"] == "pending"
    assert second["state"] == "delivered"
    assert len(client.messages) == 1
