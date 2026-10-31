"""The host's tool loop: Claude proposes, the host runs."""

import json
from dataclasses import dataclass, field

HOST_ERRORS = {
    "tool_not_offered",
    "call_budget_exceeded",
    "result_too_large",
    "tool_failed",
}


@dataclass
class Budget:
    max_turns: int = 6
    max_calls: int = 10
    max_result_chars: int = 20_000


@dataclass
class Transcript:
    answer: str = ""
    complete: bool = False
    stop: str = ""
    turns: int = 0
    calls: list[dict] = field(default_factory=list)
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
    if isinstance(question, str):
        messages = [{"role": "user", "content": question}]
    else:
        messages = list(question)
    out = Transcript()
    while out.turns < budget.max_turns:
        out.turns += 1
        reply = await model.respond(
            system, tools, messages
        )
        out.usage["input"] += reply["usage"]["input"]
        out.usage["output"] += reply["usage"]["output"]
        content = reply["content"]
        if reply["stop_reason"] != "tool_use":
            out.stop = reply["stop_reason"]
            out.complete = out.stop == "end_turn"
            out.answer = "\n".join(
                b["text"]
                for b in content
                if b["type"] == "text"
            )
            return out
        messages.append(
            {"role": "assistant", "content": content}
        )
        results = [
            await run_call(
                client, block, offered, budget, out
            )
            for block in content
            if block["type"] == "tool_use"
        ]
        messages.append(
            {"role": "user", "content": results}
        )
    out.stop = "turn_budget_exceeded"
    return out


async def run_call(client, block, offered, budget, out):
    name, args = block["name"], block["input"]
    if len(out.calls) >= budget.max_calls:
        data = host_error("call_budget_exceeded")
    elif name not in offered:
        data = host_error("tool_not_offered")
    else:
        result = await client.call_tool(
            name, args, raise_on_error=False
        )
        if result.is_error or result.data is None:
            data = host_error("tool_failed")
        else:
            data = result.data
    text = json.dumps(data)
    if len(text) > budget.max_result_chars:
        data = host_error("result_too_large")
        text = json.dumps(data)
    out.calls.append(
        {"name": name, "input": args, "result": data}
    )
    return {
        "type": "tool_result",
        "tool_use_id": block["id"],
        "content": text,
        "is_error": data.get("code") in HOST_ERRORS,
    }


def host_error(code: str) -> dict:
    return {"ok": False, "code": code}
