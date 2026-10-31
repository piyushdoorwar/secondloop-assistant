"""Compare tool contracts between two git refs.

python scripts/contract_diff.py ch05 ch14
"""

import json
import pathlib
import subprocess
import sys
import tempfile

DUMP = """
import asyncio, json, os
os.environ.update(SECONDLOOP_ENV="dev",
                  SECONDLOOP_DEV_SUBJECT="ben")
from fastmcp import Client
from secondloop.mcp_server.server import mcp
async def main():
    async with Client(mcp) as c:
        tools = await c.list_tools()
    print(json.dumps({t.name: {
        "required": t.input_schema.get("required", []),
        "properties": sorted(t.input_schema["properties"]),
        "read_only": bool(t.annotations
                          and t.annotations.read_only_hint),
        "description": t.description,
    } for t in tools}))
asyncio.run(main())
"""


def contracts(ref: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["git", "worktree", "add", "-q", tmp, ref],
            check=True,
        )
        try:
            out = subprocess.run(
                [sys.executable, "-c", DUMP],
                cwd=tmp,
                check=True,
                capture_output=True,
                text=True,
                env={
                    "PYTHONPATH": f"{tmp}/src",
                    "PATH": "/usr/bin:/bin",
                },
            ).stdout
        finally:
            subprocess.run(
                [
                    "git",
                    "worktree",
                    "remove",
                    "--force",
                    tmp,
                ],
                check=True,
            )
    return json.loads(out.strip().splitlines()[-1])


def risks(before: dict, after: dict) -> list[str]:
    found = []
    for name, old in before.items():
        new = after.get(name)
        if new is None:
            found.append(f"removed      {name}")
            continue
        for field in sorted(
            set(new["required"]) - set(old["required"])
        ):
            found.append(f"new required {name}.{field}")
        if old["read_only"] and not new["read_only"]:
            found.append(f"now writes   {name}")
        if old["description"] != new["description"]:
            found.append(f"description  {name}")
    for name, new in after.items():
        if name not in before:
            kind = "read" if new["read_only"] else "WRITE"
            found.append(f"added {kind:5}  {name}")
    return found


if __name__ == "__main__":
    old, new = sys.argv[1], sys.argv[2]
    for line in risks(contracts(old), contracts(new)):
        print(line)
