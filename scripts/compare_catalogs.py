"""Chapter 4: generated vs curated tool catalogs."""

import asyncio
import json
import re
import sys

from fastmcp import Client, FastMCP
from fastmcp.server.providers.openapi import (
    MCPType,
    RouteMap,
)

from secondloop.mcp_server.server import mcp as curated
from secondloop.ops_api.app import app

READS_ONLY = [
    RouteMap(
        pattern=r"^/internal/.*",
        mcp_type=MCPType.EXCLUDE,
    ),
    RouteMap(methods=["GET"], mcp_type=MCPType.TOOL),
    RouteMap(mcp_type=MCPType.EXCLUDE),
]


def catalogs():
    return {
        "generated": FastMCP.from_fastapi(app),
        "filtered": FastMCP.from_fastapi(
            app, route_maps=READS_ONLY
        ),
        "curated": curated,
    }


async def describe(server):
    async with Client(server) as client:
        tools = await client.list_tools()
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in tools
    ]


async def main():
    for label, server in catalogs().items():
        tools = await describe(server)
        size = len(json.dumps(tools))
        print(
            f"{label:9} {len(tools)} tools, {size} chars"
        )
        for tool in tools:
            print("   ", tool["name"])
        if "--json" in sys.argv:
            print(json.dumps(tools, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
