"""Run live evaluation cases against a tool catalog.

    python -m evals.run_eval current --repeats 3

Needs ANTHROPIC_API_KEY. Results go to evals/results/.
"""

import argparse
import os
import asyncio
import json
import pathlib
from datetime import date

from anthropic import AsyncAnthropic
from fastmcp import Client

from secondloop.host.claude import MODEL, ClaudeModel
from secondloop.host.loop import run

HERE = pathlib.Path(__file__).parent
SYSTEM = (
    "You help SecondLoop support staff investigate "
    "customer cases. Use the tools to check facts. "
    "Answer in a few sentences."
)
JUDGE = """You grade a support assistant's answer.
Question: {question}
Answer: {answer}

For each requirement, decide if the answer meets it.
must_report: {must_report}
must_not: {must_not}

Reply with JSON only:
{{"reported": [true/false per must_report],
  "violated": [true/false per must_not]}}"""


def servers():
    from evals.variants import draft
    from secondloop.mcp_server.server import mcp

    return {"draft": draft, "current": mcp}


async def grade(sdk, case, answer):
    reply = await sdk.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": JUDGE.format(
                    question=case["question"],
                    answer=answer,
                    must_report=case["must_report"],
                    must_not=case["must_not"],
                ),
            }
        ],
    )
    text = "".join(
        b.text for b in reply.content if b.type == "text"
    )
    return json.loads(
        text[text.index("{") : text.rindex("}") + 1]
    )


async def evaluate(variant, cases, repeats):
    sdk = AsyncAnthropic(timeout=60.0, max_retries=2)
    model = ClaudeModel(sdk)
    rows = []
    async with Client(servers()[variant]) as client:
        allowed = {
            t.name for t in await client.list_tools()
        }
        for case in cases:
            for n in range(repeats):
                t = await run(
                    model,
                    client,
                    case["question"],
                    allowed,
                    system=SYSTEM,
                )
                g = await grade(sdk, case, t.answer)
                rows.append(
                    {
                        "case": case["id"],
                        "run": n,
                        "pass": all(g["reported"])
                        and not any(g["violated"]),
                        "grade": g,
                        "calls": [
                            c["name"] for c in t.calls
                        ],
                        "tokens": t.usage,
                        "answer": t.answer,
                    }
                )
                print(
                    variant,
                    case["id"],
                    n,
                    rows[-1]["pass"],
                    rows[-1]["calls"],
                )
    return rows


def main():
    os.environ.setdefault("SECONDLOOP_ENV", "dev")
    os.environ.setdefault("SECONDLOOP_DEV_SUBJECT", "ben")
    parser = argparse.ArgumentParser()
    parser.add_argument("variant")
    parser.add_argument(
        "--cases", default="ch05-interface"
    )
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    cases = json.loads(
        (
            HERE / "cases" / f"{args.cases}.json"
        ).read_text()
    )
    rows = asyncio.run(
        evaluate(args.variant, cases, args.repeats)
    )
    out = (
        HERE
        / "results"
        / (
            f"{args.cases}-{args.variant}-{date.today()}.json"
        )
    )
    out.write_text(
        json.dumps(
            {
                "model": MODEL,
                "variant": args.variant,
                "rows": rows,
            },
            indent=2,
        )
    )
    passed = sum(r["pass"] for r in rows)
    print(f"{passed}/{len(rows)} passed -> {out.name}")


if __name__ == "__main__":
    main()
