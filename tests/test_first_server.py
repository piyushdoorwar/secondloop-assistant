import pytest
from fastmcp import Client

from secondloop.mcp_server.first_server import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    async with Client(mcp) as c:
        yield c


async def test_catalog_has_one_read_tool(client):
    tools = await client.list_tools()
    assert [t.name for t in tools] == ["get_order_brief"]
    assert tools[0].annotations.read_only_hint is True


async def test_known_order(client):
    result = await client.call_tool(
        "get_order_brief", {"order_ref": "SL-1042"}
    )
    order = result.data["order"]
    assert order["delivery_status"] == "delivered"
    assert order["replacement_confirmed"] is False


async def test_unknown_order_is_not_found(client):
    result = await client.call_tool(
        "get_order_brief", {"order_ref": "SL-9999"}
    )
    assert result.data == {
        "ok": False,
        "code": "not_found",
    }
