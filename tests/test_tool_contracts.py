import pytest
from fastmcp import Client

from secondloop.mcp_server import server
from secondloop.mcp_server.server import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    async with Client(mcp) as c:
        yield c


async def call(client, tool, **args):
    result = await client.call_tool(tool, args)
    return result.data


async def test_unlinked_case_points_to_candidates(
    client,
):
    data = await call(
        client, "get_order_brief", case_id="CASE-21"
    )
    assert data["code"] == "order_not_linked"
    assert data["retryable"] is False
    assert "list_candidate_orders" in data["message"]


async def test_candidates_page_through_all_orders(
    client, monkeypatch
):
    monkeypatch.setattr(server, "PAGE_SIZE", 1)
    first = await call(
        client, "list_candidate_orders", case_id="CASE-21"
    )
    assert first["has_more"] is True
    second = await call(
        client,
        "list_candidate_orders",
        case_id="CASE-21",
        cursor=first["next_cursor"],
    )
    refs = [
        c["order_ref"]
        for page in (first, second)
        for c in page["candidates"]
    ]
    assert refs == ["SL-1043", "SL-1042"]


async def test_cursor_from_another_case_is_refused(
    client, monkeypatch
):
    monkeypatch.setattr(server, "PAGE_SIZE", 1)
    page = await call(
        client, "list_candidate_orders", case_id="CASE-21"
    )
    other = await call(
        client,
        "list_candidate_orders",
        case_id="CASE-17",
        cursor=page["next_cursor"],
    )
    assert other["code"] == "cursor_invalid"


async def test_available_stock_is_not_a_reservation(
    client,
):
    data = await call(
        client,
        "get_replacement_context",
        case_id="CASE-17",
    )
    laptop = next(
        s for s in data["stock"] if s["sku"] == "LAP-14-R"
    )
    assert laptop["available"] == 2
    assert laptop["reservation"] == "none"
