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
    "sku_not_on_order": (
        False,
        "That SKU is not on the case's order.",
    ),
    "eligible_for_proposal": (False, "Unexpected."),
    "outside_window": (
        False,
        "The report is outside the policy window.",
    ),
    "no_delivery_record": (
        False,
        "No delivery is recorded for this line, so the "
        "window cannot be checked.",
    ),
    "return_already_open": (
        False,
        "A return is already open on this order.",
    ),
    "report_before_delivery": (
        False,
        "The report predates delivery; a person must "
        "check the case.",
    ),
    "returnable_list_incomplete": (
        False,
        "Too many returnable lines to check safely.",
    ),
    "quantity_not_returnable": (
        False,
        "That quantity is not returnable on this order.",
    ),
    "writes_paused": (
        False,
        "New proposals are paused. Investigation still "
        "works; tell the employee to try later.",
    ),
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
