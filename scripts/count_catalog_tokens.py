"""Count the input tokens each catalog adds to a request.

Uses Anthropic's free token-counting endpoint; needs
ANTHROPIC_API_KEY. No model output is generated.
"""

import asyncio
import os

from anthropic import Anthropic

from scripts.compare_catalogs import catalogs, describe

MODEL = os.environ.get(
    "CLAUDE_MODEL", "claude-sonnet-5-5"
)
QUESTION = [
    {"role": "user", "content": "What do we know?"}
]


async def main():
    sdk = Anthropic()
    base = sdk.messages.count_tokens(
        model=MODEL, messages=QUESTION
    ).input_tokens
    for label, server in catalogs().items():
        tools = await describe(server)
        total = sdk.messages.count_tokens(
            model=MODEL, messages=QUESTION, tools=tools
        ).input_tokens
        print(
            f"{label:9} {len(tools)} tools "
            f"+{total - base} tokens"
        )


if __name__ == "__main__":
    asyncio.run(main())
