"""The SecondLoop investigation server."""

import logging

from typing import Annotated

import anyio
from fastmcp import FastMCP
from pydantic import Field

from secondloop.cases import load_cases
from secondloop.cursors import open_cursor, seal
from secondloop.identity import (
    Denied,
    authorize_case,
    current_principal,
)
from pydantic import Field as F
from secondloop.mcp_server.auth import build_auth
from secondloop.ops_client import (
    OpsError,
    get_json,
    ops_http,
)
from secondloop.policy import assess
from secondloop.results import failure, ok
from secondloop.shopify.client import ShopifyError
from secondloop.shopify.customers import read_candidates
from secondloop.shopify.factory import admin_client
from secondloop.shopify.orders import read_order_brief
from secondloop.shopify.returns import (
    Incomplete,
    damage_reason_id,
    returnable_lines,
)
from secondloop.shopify.shop import read_timezone
from secondloop.slack import escape, operations_channel
from secondloop.workflow import proposals
from secondloop.workflow.db import connect

mcp = FastMCP(
    "SecondLoop investigations",
    version="0.8.0",
    auth=build_auth(),
)
log = logging.getLogger("secondloop.mcp")
CASES = load_cases()
PAGE_SIZE = 3

CaseId = Annotated[str, Field(pattern=r"^CASE-\d{1,8}$")]
Cursor = Annotated[str | None, Field(max_length=512)]


def permitted_case(case_id, role="support_read"):
    """Return (case, None) or (None, error_code)."""
    case = CASES.get(case_id)
    if case is None:
        return None, "case_not_found"
    try:
        authorize_case(current_principal(), case, role)
    except Denied as denied:
        log.info("denied %s: %s", case_id, denied)
        return None, "case_not_found"
    return case, None


def case_brief(case):
    """Return (brief, None) or (None, error_code)."""
    if case.order_id is None:
        return None, "order_not_linked"
    try:
        brief = read_order_brief(
            admin_client(case.shop), case.order_id
        )
    except ShopifyError as error:
        return None, error.code
    if brief is None:
        return None, "order_not_found"
    return brief, None


@mcp.tool(annotations={"readOnlyHint": True})
def get_order_brief(case_id: CaseId) -> dict:
    """Read the order linked to a support case.

    Returns order, shipment and return facts from
    Shopify, line by line. A line's shipment is
    NOT_SHIPPED, IN_TRANSIT, DELIVERED or another
    carrier status; delivered_at is set only for
    DELIVERED lines. Does not decide return
    eligibility, reserve stock, or create anything.
    """
    case, error = permitted_case(case_id)
    if error:
        return failure(error)
    brief, error = case_brief(case)
    if error:
        return failure(error)
    return ok(brief=brief.model_dump())


@mcp.tool(annotations={"readOnlyHint": True})
def list_candidate_orders(
    case_id: CaseId, cursor: Cursor = None
) -> dict:
    """Recent orders of the case's customer, newest first.

    Use when a case has no linked order, so the
    employee can say which order they mean. Never pick
    one yourself. Returns at most three orders; if
    has_more is true, pass next_cursor to see more.
    """
    case, error = permitted_case(case_id)
    if error:
        return failure(error)
    if case.customer_id is None:
        return failure("case_not_found")
    after = None
    if cursor:
        try:
            after = open_cursor(case_id, cursor)
        except ValueError:
            return failure("cursor_invalid")
    try:
        page = read_candidates(
            admin_client(case.shop),
            case.customer_id,
            first=PAGE_SIZE,
            after=after,
        )
    except ShopifyError as error:
        return failure(error.code)
    if page is None:
        return failure("case_not_found")
    next_cursor = None
    if page.has_more and page.vendor_cursor:
        next_cursor = seal(case_id, page.vendor_cursor)
    return ok(
        candidates=[
            c.model_dump() for c in page.candidates
        ],
        has_more=page.has_more,
        next_cursor=next_cursor,
    )


@mcp.tool(annotations={"readOnlyHint": True})
async def get_replacement_context(
    case_id: CaseId,
) -> dict:
    """Stock and damage policy for a case's products.

    Covers only the SKUs on the case's order. For each
    SKU, reservation is "held_for_this_case" only if a
    unit is already reserved for this case; available
    stock is not a reservation. Does not reserve a unit
    or request a replacement.
    """
    case, error = permitted_case(case_id)
    if error:
        return failure(error)
    brief, error = await anyio.to_thread.run_sync(
        case_brief, case
    )
    if error:
        return failure(error)
    skus = sorted({l.sku for l in brief.lines if l.sku})
    async with ops_http() as http:
        try:
            current = await get_json(
                http, "/policies/damage"
            )
            policy = await get_json(
                http,
                f"/policies/damage/{current['version']}",
            )
            stock = [
                await get_json(
                    http,
                    f"/stock/{sku}?case_id={case_id}",
                )
                for sku in skus
            ]
        except OpsError as error:
            return failure(error.code)
    return ok(
        policy=policy,
        stock=[stock_fact(s) for s in stock],
    )


def stock_fact(row: dict) -> dict:
    held = row["held_for_case"]
    return {
        "sku": row["sku"],
        "on_hand": row["on_hand"],
        "available": row["available"],
        "reservation": (
            "held_for_this_case" if held else "none"
        ),
    }


async def read_policy(version=None) -> dict:
    async with ops_http() as http:
        if version is None:
            current = await get_json(
                http, "/policies/damage"
            )
            version = current["version"]
        return await get_json(
            http, f"/policies/damage/{version}"
        )


@mcp.resource(
    "policy://damage/current",
    mime_type="application/json",
)
async def current_damage_policy() -> dict:
    """The damage-return policy in force today."""
    return await read_policy()


@mcp.resource(
    "policy://damage/{version}",
    mime_type="application/json",
)
async def damage_policy(version: int) -> dict:
    """One version of the damage-return policy."""
    return await read_policy(version)


@mcp.prompt
def investigate_damage(case_id: str) -> str:
    """Start a read-only investigation of damage."""
    return (
        f"Investigate support case {case_id}, a report "
        "of an item that arrived damaged.\n"
        "1. Read the order with get_order_brief.\n"
        "2. Check the return window with "
        "check_return_window for the damaged SKU.\n"
        "3. Read stock with get_replacement_context.\n"
        "Report the facts, the policy version used, and "
        "what is still unknown. Do not promise a "
        "replacement or a date. Do not create anything."
    )


@mcp.tool(annotations={"readOnlyHint": True})
async def check_return_window(
    case_id: CaseId, sku: str
) -> dict:
    """Apply the current damage policy to one order line.

    Counts calendar days from delivery to the case's
    report date in the store's time zone. Outcomes:
    eligible_for_proposal, outside_window,
    no_delivery_record, return_already_open,
    report_before_delivery. eligible_for_proposal
    means a return may be proposed for approval; it is
    not an approval.
    """
    case, error = permitted_case(case_id)
    if error:
        return failure(error)
    brief, error = await anyio.to_thread.run_sync(
        case_brief, case
    )
    if error:
        return failure(error)
    line = next(
        (l for l in brief.lines if l.sku == sku), None
    )
    if line is None:
        return failure("sku_not_on_order")
    try:
        timezone = await anyio.to_thread.run_sync(
            read_timezone, admin_client(case.shop)
        )
    except ShopifyError as error:
        return failure(error.code)
    try:
        policy = await read_policy()
    except OpsError as error:
        return failure(error.code)
    result = assess(
        policy,
        line,
        brief.open_returns,
        case.reported_at,
        timezone,
    )
    return ok(
        order_ref=brief.order_ref,
        sku=sku,
        **result.model_dump(),
    )


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def propose_return(
    case_id: CaseId,
    sku: str,
    quantity: Annotated[int, F(ge=1, le=5)] = 1,
) -> dict:
    """Prepare a damage return for a second person to approve.

    Creates a proposal only. Nothing changes in Shopify
    until another employee approves this exact proposal
    in the support console. Requires the return window
    check to be eligible_for_proposal.
    """
    case, error = permitted_case(
        case_id, "return_request"
    )
    if error:
        return failure(error)
    brief, error = case_brief(case)
    if error:
        return failure(error)
    line = next(
        (l for l in brief.lines if l.sku == sku), None
    )
    if line is None:
        return failure("sku_not_on_order")
    client = admin_client(case.shop)
    try:
        policy = anyio.from_thread.run(read_policy)
        decision = assess(
            policy,
            line,
            brief.open_returns,
            case.reported_at,
            read_timezone(client),
        )
        if decision.outcome != "eligible_for_proposal":
            return failure(decision.outcome)
        lines = returnable_lines(client, case.order_id)
        reason = damage_reason_id(client)
    except ShopifyError as error:
        return failure(error.code)
    except Incomplete:
        return failure("returnable_list_incomplete")
    match = next((l for l in lines if l.sku == sku), None)
    if match is None or match.quantity < quantity:
        return failure("quantity_not_returnable")
    spec = {
        "order_id": case.order_id,
        "order_ref": case.order_ref,
        "sku": sku,
        "fulfillment_line_item_id": match.fulfillment_line_item_id,
        "quantity": quantity,
        "reason_definition_id": reason,
        "policy_version": decision.policy_version,
    }
    with connect() as conn:
        row = proposals.create(
            conn,
            "return",
            case,
            current_principal().subject,
            spec,
            decision.policy_version,
        )
    return ok(
        proposal_id=row["id"],
        state="pending_approval",
        expires_at=row["expires_at"].isoformat(),
        preview=(
            f"Return {quantity} x {sku} from "
            f"{case.order_ref} as damaged "
            f"(policy v{decision.policy_version})."
        ),
    )


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def propose_escalation(
    case_id: CaseId,
    summary: Annotated[
        str, F(min_length=1, max_length=400)
    ],
) -> dict:
    """Prepare a note to the operations Slack channel.

    The channel is fixed by SecondLoop. The note says
    the case, the order and your summary; keep customer
    personal details out of the summary. Posts only
    after a second employee approves the exact text.
    """
    case, error = permitted_case(
        case_id, "return_request"
    )
    if error:
        return failure(error)
    text = (
        f"Replacement review: {case.case_id} "
        f"({case.order_ref or 'no linked order'})\n"
        f"Summary: {escape(summary)}"
    )
    spec = {"channel": operations_channel(), "text": text}
    with connect() as conn:
        row = proposals.create(
            conn,
            "escalation",
            case,
            current_principal().subject,
            spec,
        )
    return ok(
        proposal_id=row["id"],
        state="pending_approval",
        expires_at=row["expires_at"].isoformat(),
        preview=text,
    )


@mcp.tool(annotations={"readOnlyHint": True})
def get_case_activity(case_id: CaseId) -> dict:
    """Proposals and operations for a case, newest first.

    An operation in state unknown has been sent but not
    confirmed; do not propose the same action again.
    """
    case, error = permitted_case(case_id)
    if error:
        return failure(error)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.id AS proposal_id, p.kind,
                   p.state AS proposal_state,
                   o.id AS operation_id,
                   o.state AS operation_state,
                   o.vendor_ref
            FROM proposals p
            LEFT JOIN operations o
              ON o.proposal_id = p.id
            WHERE p.case_id = %s
            ORDER BY p.created_at DESC LIMIT 10
            """,
            (case_id,),
        ).fetchall()
    return ok(activity=rows)


if __name__ == "__main__":
    mcp.run()
