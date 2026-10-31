"""Deliver follow-up events written with an operation."""

from secondloop import slack

CLAIM_EVENT = """
SELECT * FROM outbox
WHERE state = 'pending'
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 1
"""


def text_for(event) -> str:
    p = event["payload"]
    return (
        f"Return {p['return']} created for "
        f"{p['case_id']} ({p['order_ref']})."
    )


def deliver_one(conn, client, channel) -> dict | None:
    """Post one pending event; check first if retried."""
    with conn.transaction():
        event = conn.execute(CLAIM_EVENT).fetchone()
        if event is None:
            return None
        ts = None
        if event["attempts"] > 0:
            since = event["created_at"].timestamp() - 60
            ts = slack.find_posted(
                client, channel, event["id"], since
            )
        if ts is None:
            conn.execute(
                "UPDATE outbox SET attempts = "
                "attempts + 1 WHERE id = %s",
                (event["id"],),
            )
    if ts is None:
        try:
            ts = slack.post(
                client,
                channel,
                text_for(event),
                event["id"],
            )
        except Exception:
            return {"id": event["id"], "state": "pending"}
    conn.execute(
        "UPDATE outbox SET state = 'delivered', "
        "vendor_ref = %s WHERE id = %s",
        (ts, event["id"]),
    )
    conn.commit()
    return {
        "id": event["id"],
        "state": "delivered",
        "vendor_ref": ts,
    }
