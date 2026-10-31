"""Serve the MCP server over Streamable HTTP.

python -m secondloop.mcp_server.http
"""

import os
import sys

from starlette.responses import JSONResponse

from secondloop.cursors import KEY as CURSOR_KEY
from secondloop.mcp_server.server import mcp
from secondloop.workflow.db import connect

READY = {"ok": False}


def startup_problems() -> list[str]:
    problems = []
    if mcp.auth is None:
        problems.append("no token verifier configured")
    if os.environ.get("SECONDLOOP_ENV") == "dev":
        problems.append(
            "SECONDLOOP_ENV=dev is not allowed"
        )
    if CURSOR_KEY == b"dev-only-cursor-key":
        problems.append(
            "CURSOR_KEY is the development key"
        )
    if os.environ.get("SHOPIFY_MODE", "fake") != "live":
        if os.environ.get("ALLOW_FAKE_SHOPIFY") != "1":
            problems.append("SHOPIFY_MODE is not live")
    return problems


@mcp.custom_route("/livez", methods=["GET"])
async def livez(request):
    return JSONResponse({"status": "alive"})


@mcp.custom_route("/readyz", methods=["GET"])
async def readyz(request):
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
    except Exception:
        return JSONResponse(
            {"status": "no_database"}, status_code=503
        )
    return JSONResponse({"status": "ready"})


def main():
    problems = startup_problems()
    if problems:
        for problem in problems:
            print(
                "refusing to start:",
                problem,
                file=sys.stderr,
            )
        sys.exit(2)
    mcp.run(
        transport="http",
        host=os.environ.get("BIND_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8001")),
    )


if __name__ == "__main__":
    main()
