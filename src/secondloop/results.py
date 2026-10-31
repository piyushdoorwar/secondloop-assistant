"""Stable result shapes for every tool."""

from datetime import datetime, timezone

# code -> (retryable, what the employee should know)
FAILURES = {
    "case_not_found": (False, "No such case."),
    "order_not_linked": (
        False,
        "The case has no linked order. Use "
        "list_candidate_orders and ask the employee "
        "which order they mean.",
    ),
    "order_not_found": (
        False,
        "The linked order no longer exists.",
    ),
    "not_authorized": (
        False,
        "The store connection needs attention.",
    ),
    "access_denied": (
        False,
        "The app lacks access to this data.",
    ),
    "throttled": (True, "Shopify is busy. Try later."),
    "ops_timeout": (
        True,
        "The operations service did not answer.",
    ),
    "ops_not_found": (False, "Unknown policy or SKU."),
    "cursor_invalid": (
        False,
        "The continuation token is not valid for this "
        "case. Start again without a cursor.",
    ),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )


def ok(**facts) -> dict:
    return {"ok": True, "observed_at": now(), **facts}


def failure(code: str) -> dict:
    retryable, message = FAILURES.get(
        code, (False, "Unexpected failure.")
    )
    return {
        "ok": False,
        "code": code,
        "retryable": retryable,
        "message": message,
    }
