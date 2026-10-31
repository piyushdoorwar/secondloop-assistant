import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from scripts.compare_catalogs import catalogs
from secondloop.ops_api.app import app

pytestmark = pytest.mark.anyio


async def names(server):
    async with Client(server) as client:
        return {t.name for t in await client.list_tools()}


async def test_generation_exposes_writes_and_internals():
    found = await names(catalogs()["generated"])
    assert {"create_replacement", "flush_cache"} <= found


async def test_route_maps_keep_only_public_reads():
    found = await names(catalogs()["filtered"])
    assert found == {
        "current_damage_policy",
        "damage_policy_version",
        "warehouse_stock",
        "list_replacements",
    }


async def test_every_write_is_a_proposal():
    async with Client(catalogs()["curated"]) as client:
        tools = await client.list_tools()
    writes = {
        t.name
        for t in tools
        if not t.annotations.read_only_hint
    }
    assert writes == {
        "propose_return",
        "propose_escalation",
    }


async def test_context_covers_only_the_case_skus(
    monkeypatch,
):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    async with Client(catalogs()["curated"]) as client:
        result = await client.call_tool(
            "get_replacement_context",
            {"case_id": "CASE-18"},
        )
    skus = [s["sku"] for s in result.data["stock"]]
    assert skus == ["HDP-BT-R", "LAP-14-R"]


def test_service_refuses_a_second_replacement():
    api = TestClient(app)
    body = {
        "case_id": "CASE-90",
        "sku": "LAP-14-R",
        "quantity": 1,
    }
    first = api.post("/replacements", json=body)
    second = api.post("/replacements", json=body)
    assert first.status_code == 201
    assert second.status_code == 409
