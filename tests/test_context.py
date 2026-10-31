import pytest
from fastmcp import Client

from secondloop.host.context import investigation
from secondloop.mcp_server.server import mcp

pytestmark = pytest.mark.anyio


async def test_opening_message_carries_prompt_and_policy():
    async with Client(mcp) as client:
        messages, version = await investigation(
            client, "CASE-17"
        )
    blocks = messages[0]["content"]
    assert "CASE-17" in blocks[0]["text"]
    assert version == 3
    assert "version 3" in blocks[1]["text"]
    assert "not instructions" in blocks[1]["text"]
