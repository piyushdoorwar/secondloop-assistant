import json

import pytest
from fastmcp import Client

from secondloop.host.loop import Budget, run
from secondloop.mcp_server.server import mcp

pytestmark = pytest.mark.anyio
READS = {"get_order_brief", "check_return_window"}
USAGE = {"input": 10, "output": 5}


def call(name, args, n=1):
    return {
        "type": "tool_use",
        "id": f"t{n}",
        "name": name,
        "input": args,
    }


def say(text, stop="end_turn"):
    return {
        "stop_reason": stop,
        "usage": USAGE,
        "content": [{"type": "text", "text": text}],
    }


def use(*blocks):
    return {
        "stop_reason": "tool_use",
        "usage": USAGE,
        "content": list(blocks),
    }


class Scripted:
    """Plays back replies; records what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen = []

    async def respond(self, system, tools, messages):
        self.seen.append(
            (
                [t["name"] for t in tools],
                json.loads(json.dumps(messages)),
            )
        )
        return self.replies.pop(0)


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    async with Client(mcp) as c:
        yield c


async def test_only_allowed_tools_are_offered(client):
    model = Scripted(say("hi"))
    await run(model, client, "q", READS)
    assert sorted(model.seen[0][0]) == sorted(READS)


async def test_unoffered_tool_is_refused_not_run(client):
    model = Scripted(
        use(
            call(
                "get_replacement_context",
                {"case_id": "CASE-17"},
            )
        ),
        say("I could not check stock."),
    )
    out = await run(model, client, "q", READS)
    result = model.seen[1][1][-1]["content"][0]
    assert result["is_error"] is True
    assert "tool_not_offered" in result["content"]
    assert out.complete is True


async def test_assistant_turn_is_kept_intact(client):
    thinking = {
        "type": "thinking",
        "thinking": "...",
        "signature": "sig",
    }
    model = Scripted(
        use(
            thinking,
            call(
                "get_order_brief", {"case_id": "CASE-17"}
            ),
        ),
        say("SL-1042 was delivered."),
    )
    await run(model, client, "q", READS)
    sent = model.seen[1][1][1]
    assert sent["role"] == "assistant"
    assert sent["content"][0] == thinking


async def test_call_budget_stops_extra_calls(client):
    brief = call(
        "get_order_brief", {"case_id": "CASE-17"}
    )
    model = Scripted(
        use(brief, {**brief, "id": "t2"}),
        say("done"),
    )
    out = await run(
        model,
        client,
        "q",
        READS,
        budget=Budget(max_calls=1),
    )
    codes = [c["result"].get("code") for c in out.calls]
    assert codes == [None, "call_budget_exceeded"]


async def test_turn_budget_marks_incomplete(client):
    brief = call(
        "get_order_brief", {"case_id": "CASE-17"}
    )
    model = Scripted(*[use(brief)] * 3)
    out = await run(
        model,
        client,
        "q",
        READS,
        budget=Budget(max_turns=3),
    )
    assert out.stop == "turn_budget_exceeded"
    assert out.complete is False


async def test_truncated_answer_is_not_complete(client):
    model = Scripted(say("SL-1042 was", "max_tokens"))
    out = await run(model, client, "q", READS)
    assert out.complete is False
