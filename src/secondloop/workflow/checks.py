"""Re-check the world just before an operation runs."""

import json

import anyio

from secondloop.cases import DATA, load_cases
from secondloop.mcp_server.server import read_policy
from secondloop.shopify.client import ShopifyError
from secondloop.shopify.factory import admin_client
from secondloop.shopify.returns import returnable_lines
from secondloop.slack import operations_channel


def roles_of(subject) -> set:
    """Current roles from the directory, not the token."""
    rows = json.loads(
        (DATA / "employees.json").read_text()
    )
    for row in rows:
        if row["sub"] == subject:
            return set(row["roles"])
    return set()


def current_checks(op) -> str | None:
    """None if still valid, else the reason it is not."""
    if "return_request" not in roles_of(
        op["requested_by"]
    ):
        return "requester_lost_role"
    if "return_approve" not in roles_of(
        op["approved_by"]
    ):
        return "approver_lost_role"
    spec = op["spec"]
    if op["kind"] == "escalation":
        if spec["channel"] != operations_channel():
            return "channel_changed"
        return None
    policy = anyio.run(read_policy)
    if policy["version"] != spec["policy_version"]:
        return "policy_changed"
    case = load_cases()[op["case_id"]]
    try:
        lines = returnable_lines(
            admin_client(case.shop), spec["order_id"]
        )
    except ShopifyError as error:
        return f"recheck_failed:{error.code}"
    for line in lines:
        if (
            line.fulfillment_line_item_id
            == spec["fulfillment_line_item_id"]
        ):
            if line.quantity >= spec["quantity"]:
                return None
    return "no_longer_returnable"
