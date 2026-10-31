"""The host's tool loop: Claude proposes, the host runs."""

import json
from dataclasses import dataclass, field


@dataclass
class Budget:
    max_turns: int = 6
    max_calls: int = 10


@dataclass
class Transcript:
    answer: str = ""
    calls: list[dict] = field(default_factory=list)
    stop: str = ""
    usage: dict = field(
        default_factory=lambda: {"input": 0, "output": 0}
    )


def to_model_tool(tool) -> dict:
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.input_schema,
    }


async def run(
    model,
    client,
    question,
    allowed,
    budget=Budget(),
    system="",
):
    """Answer one question with the allowed tools."""
    catalog = await client.list_tools()
    tools = [
        to_model_tool(t)
        for t in catalog
        if t.name in allowed
    ]
    offered = {t["name"] for t in tools}
    messages = [{"role": "user", "content": question}]
    out = Transcript()
    for _ in range(budget.max_turns):
        reply = await model.respond(
            system, tools, messages
        )
        out.usage["input"] += reply["usage"]["input"]
        out.usage["output"] += reply["usage"]["output"]
        content = reply["content"]
        if reply["stop_reason"] != "tool_use":
            out.stop = reply["stop_reason"]
            out.answer = "\n".join(
                b["text"]
                for b in content
                if b["type"] == "text"
            )
            return out
        messages.append(
            {"role": "assistant", "content": content}
        )
        results = []
        for block in content:
            if block["type"] != "tool_use":
                continue
            results.append(
                await run_call(
                    client, block, offered, budget, out
                )
            )
        messages.append(
            {"role": "user", "content": results}
        )
    out.stop = "turn_budget_exceeded"
    return out


async def run_call(client, block, offered, budget, out):
    name, args = block["name"], block["input"]
    if len(out.calls) >= budget.max_calls:
        data = {
            "ok": False,
            "code": "call_budget_exceeded",
        }
    elif name not in offered:
        data = {"ok": False, "code": "tool_not_offered"}
    else:
        result = await client.call_tool(
            name, args, raise_on_error=False
        )
        data = (
            result.data
            if result.data is not None
            else {
                "ok": False,
                "code": "tool_failed",
            }
        )
    out.calls.append(
        {"name": name, "input": args, "result": data}
    )
    return {
        "type": "tool_result",
        "tool_use_id": block["id"],
        "content": json.dumps(data),
    }
