"""Call SecondLoop's operations service."""

import os

import httpx2 as httpx


def ops_http() -> httpx.AsyncClient:
    url = os.environ.get("OPS_API_URL")
    if url:
        return httpx.AsyncClient(
            base_url=url, timeout=5.0
        )
    from secondloop.ops_api.app import app

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://ops.local",
        timeout=5.0,
    )


class OpsError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


async def get_json(http, path: str) -> dict:
    try:
        response = await http.get(path)
    except httpx.TimeoutException:
        raise OpsError("ops_timeout")
    if response.status_code == 404:
        raise OpsError("ops_not_found")
    if response.status_code >= 400:
        raise OpsError("ops_error")
    return response.json()
