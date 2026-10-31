"""Claude as the model behind the host loop."""

import os

from anthropic import AsyncAnthropic

MODEL = os.environ.get(
    "CLAUDE_MODEL", "claude-sonnet-5-5"
)


class ClaudeModel:
    def __init__(
        self, sdk=None, model=MODEL, max_tokens=800
    ):
        self.sdk = sdk or AsyncAnthropic(
            timeout=60.0, max_retries=2
        )
        self.model = model
        self.max_tokens = max_tokens

    async def respond(self, system, tools, messages):
        reply = await self.sdk.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        return {
            "stop_reason": reply.stop_reason,
            "content": [
                b.model_dump(
                    mode="json", exclude_none=True
                )
                for b in reply.content
            ],
            "usage": {
                "input": reply.usage.input_tokens,
                "output": reply.usage.output_tokens,
            },
        }
