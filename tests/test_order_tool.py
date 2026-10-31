import pytest
from fastmcp import Client

from secondloop.mcp_server.server import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    async with Client(mcp) as c:
        yield c


async def brief(client, case_id):
    result = await client.call_tool(
        "get_order_brief", {"case_id": case_id}
    )
    return result.data


async def test_case_17_was_delivered(client):
    data = await brief(client, "CASE-17")
    assert data["brief"]["order_ref"] == "SL-1042"
    laptop = data["brief"]["lines"][0]
    assert laptop["sku"] == "LAP-14-R"
    assert laptop["delivered_at"].startswith("2026-10-26")


async def test_partial_order_has_no_delivery(client):
    data = await brief(client, "CASE-18")
    lines = {l["sku"]: l for l in data["brief"]["lines"]}
    assert lines["LAP-14-R"]["shipment"] == "NOT_SHIPPED"
    assert lines["HDP-BT-R"]["shipment"] == "IN_TRANSIT"
    assert lines["HDP-BT-R"]["delivered_at"] is None


async def test_existing_return_is_reported(client):
    data = await brief(client, "CASE-19")
    assert data["brief"]["open_returns"] == 1


async def test_unknown_case(client):
    data = await brief(client, "CASE-99")
    assert data["code"] == "case_not_found"


@pytest.mark.live
async def test_live_store_matches_recording(monkeypatch):
    monkeypatch.setenv("SHOPIFY_MODE", "live")
    async with Client(mcp) as live:
        data = await brief(live, "CASE-17")
    assert data["brief"]["fulfillment_status"] == (
        "FULFILLED"
    )
