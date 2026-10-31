import json

import pytest
from fastmcp import Client

from secondloop.mcp_server.server import mcp
from secondloop.ops_api import app as ops
from secondloop.policy import assess
from secondloop.shopify.orders import Line

POLICY = ops.POLICIES[3]
NY = "America/New_York"


def line(delivered_at):
    return Line(
        sku="LAP-14-R",
        ordered=1,
        current=1,
        unshipped=0,
        shipment="DELIVERED",
        delivered_at=delivered_at,
    )


def test_day_thirty_counts_in_store_time():
    # 23:30 in New York on day 30 is already day 31
    # in UTC. The store's calendar decides.
    result = assess(
        POLICY,
        line("2026-10-01T15:00:00Z"),
        0,
        "2026-11-01T03:30:00Z",
        NY,
    )
    assert result.reported_on == "2026-10-31"
    assert result.days_after_delivery == 30
    assert result.outcome == "eligible_for_proposal"


def test_day_thirty_one_is_outside():
    result = assess(
        POLICY,
        line("2026-10-01T15:00:00Z"),
        0,
        "2026-11-01T15:00:00Z",
        NY,
    )
    assert result.outcome == "outside_window"


def test_missing_delivery_is_not_a_rejection():
    result = assess(
        POLICY, line(None), 0, "2026-10-30T14:00:00Z", NY
    )
    assert result.outcome == "no_delivery_record"


def test_report_before_delivery_is_flagged():
    result = assess(
        POLICY,
        line("2026-10-26T15:42:00Z"),
        0,
        "2026-10-25T12:00:00Z",
        NY,
    )
    assert result.outcome == "report_before_delivery"


@pytest.mark.anyio
async def test_policy_is_a_versioned_resource():
    async with Client(mcp) as client:
        current = await client.read_resource(
            "policy://damage/current"
        )
        old = await client.read_resource(
            "policy://damage/2"
        )
    assert json.loads(current[0].text)["version"] == 3
    assert json.loads(old[0].text)["window_days"] == 14


@pytest.mark.anyio
async def test_window_check_uses_the_current_version(
    monkeypatch,
):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    monkeypatch.setattr(ops, "CURRENT_POLICY", 2)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "check_return_window",
            {"case_id": "CASE-17", "sku": "LAP-14-R"},
        )
    assert result.data["policy_version"] == 2
    assert result.data["window_days"] == 14
