"""Call the running HTTP stack as Ben and as Ana.

    python scripts/smoke_http.py http://127.0.0.1:8100 \
        http://127.0.0.1:8001
"""

import asyncio
import sys

import httpx2 as httpx
from fastmcp import Client


def token(idp, subject, audience="secondloop-mcp"):
    response = httpx.post(
        f"{idp}/token",
        json={"subject": subject, "audience": audience},
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def brief(mcp_url, bearer):
    async with Client(f"{mcp_url}/mcp", auth=bearer) as c:
        result = await c.call_tool(
            "get_order_brief", {"case_id": "CASE-17"}
        )
    return result.data


if __name__ == "__main__":
    idp, mcp_url = sys.argv[1], sys.argv[2]
    print("livez", httpx.get(f"{mcp_url}/livez").json())
    print("readyz", httpx.get(f"{mcp_url}/readyz").json())
    ben = asyncio.run(brief(mcp_url, token(idp, "ben")))
    print(
        "ben",
        ben["ok"],
        ben["brief"]["order_ref"],
        ben["brief"]["open_returns"],
    )
    ana = asyncio.run(brief(mcp_url, token(idp, "ana")))
    print("ana", ana)
