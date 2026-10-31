"""Replay recorded Admin API replies for tests.

Recordings in data/shopify_recorded/ were captured
from the companion development store. The fake answers
only operations it has a recording for.
"""

import json
import pathlib

import httpx2 as httpx

RECORDED = (
    pathlib.Path(__file__).parents[3]
    / "data"
    / "shopify_recorded"
)


def _load() -> dict:
    replies = {}
    for path in RECORDED.glob("*.json"):
        item = json.loads(path.read_text())
        key = (
            item["operation"],
            json.dumps(item["variables"], sort_keys=True),
        )
        replies[key] = item["response"]
    return replies


def fake_transport() -> httpx.MockTransport:
    replies = _load()

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(
            "/oauth/access_token"
        ):
            return httpx.Response(
                200,
                json={
                    "access_token": "fake-token",
                    "expires_in": 86399,
                },
            )
        body = json.loads(request.content)
        operation = (
            body["query"].split("(")[0].split()[-1]
        )
        key = (
            operation,
            json.dumps(body["variables"], sort_keys=True),
        )
        if key not in replies:
            error = {
                "message": f"Unrecorded: {operation}",
                "extensions": {"code": "FAKE_UNRECORDED"},
            }
            return httpx.Response(
                200, json={"errors": [error]}
            )
        return httpx.Response(200, json=replies[key])

    return httpx.MockTransport(handle)
