"""Find out what happened to operations we lost track of."""

import time

from secondloop import slack
from secondloop.cases import load_cases
from secondloop.shopify.factory import admin_client
from secondloop.shopify.returns import order_returns

STALE_LEASE = """
UPDATE operations
SET state = 'unknown', detail = 'worker_lease_expired',
    lease_until = NULL, updated_at = now()
WHERE state = 'submitting' AND lease_until < now()
RETURNING id
"""


def expire_leases(conn) -> list[str]:
    """A worker that vanished mid-send leaves unknowns."""
    rows = conn.execute(STALE_LEASE).fetchall()
    conn.commit()
    return [r["id"] for r in rows]


def matching_return(returns, spec):
    """Returns that contain the approved line and qty."""
    found = []
    for ret in returns:
        for item in ret["returnLineItems"]["nodes"]:
            fli = (
                item.get("fulfillmentLineItem") or {}
            ).get("id")
            if (
                fli == spec["fulfillment_line_item_id"]
                and item["quantity"] == spec["quantity"]
            ):
                found.append(ret)
    return found


def evidence_for(op, shopify=None, slack_client=None):
    """(state, vendor_ref, detail) from vendor evidence."""
    spec = op["spec"]
    if op["kind"] == "return":
        case = load_cases()[op["case_id"]]
        returns = order_returns(
            shopify or admin_client(case.shop),
            spec["order_id"],
        )
        found = matching_return(returns, spec)
        if len(found) == 1:
            return "confirmed", found[0]["name"], None
        if not found:
            return "needs_review", None, "no_return_found"
        return "needs_review", None, "several_returns"
    since = op["submitted_at"].timestamp() - 60
    ts = slack.find_posted(
        slack_client or slack.slack_client(),
        spec["channel"],
        op["id"],
        since,
    )
    if ts:
        return "confirmed", ts, None
    return "needs_review", None, "no_message_found"


def reconcile(conn, **vendors) -> list[dict]:
    done = []
    unknown = conn.execute(
        "SELECT * FROM operations WHERE state = 'unknown'"
    ).fetchall()
    for op in unknown:
        state, ref, detail = evidence_for(op, **vendors)
        conn.execute(
            "UPDATE operations SET state = %s, "
            "vendor_ref = %s, detail = %s, "
            "updated_at = now() WHERE id = %s",
            (state, ref, detail, op["id"]),
        )
        conn.commit()
        done.append(
            {
                "id": op["id"],
                "state": state,
                "vendor_ref": ref,
            }
        )
    return done
