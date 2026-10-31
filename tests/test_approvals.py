import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.server.auth.providers.jwt import RSAKeyPair

from secondloop.console import app as console
from secondloop.mcp_server.server import mcp

pytestmark = pytest.mark.anyio
KEYS = RSAKeyPair.generate()
ISSUER = "https://idp.secondloop.test"
STORE = ["secondloop-lab"]


def bearer(sub, roles, stores=STORE):
    raw = KEYS.create_token(
        subject=sub,
        issuer=ISSUER,
        audience="secondloop-console",
        additional_claims={
            "stores": stores,
            "roles": roles,
        },
    )
    return {"Authorization": f"Bearer {raw}"}


LEENA = bearer("leena", ["return_approve"])
MIRA = bearer(
    "mira", ["return_request", "return_approve"]
)
ANA = bearer("ana", ["return_approve"], ["northwind-dev"])


@pytest.fixture
def api(monkeypatch, db):
    monkeypatch.setenv(
        "CONSOLE_PUBLIC_KEY", KEYS.public_key
    )
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    return TestClient(console.app)


@pytest.fixture
async def as_mira(monkeypatch, db):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    monkeypatch.setenv("SECONDLOOP_DEV_SUBJECT", "mira")
    monkeypatch.setenv(
        "SLACK_OPERATIONS_CHANNEL", "C-OPS"
    )
    async with Client(mcp) as client:
        yield client


async def propose(client, **args):
    result = await client.call_tool(
        "propose_return",
        {
            "case_id": "CASE-17",
            "sku": "LAP-14-R",
            **args,
        },
    )
    return result.data


async def test_ben_cannot_propose(monkeypatch, db):
    monkeypatch.setenv("SHOPIFY_MODE", "fake")
    async with Client(mcp) as client:
        data = await propose(client)
    assert data["code"] == "case_not_found"


async def test_proposal_waits_for_approval(as_mira, api):
    data = await propose(as_mira)
    assert data["state"] == "pending_approval"
    shown = api.get(
        f"/proposals/{data['proposal_id']}", headers=LEENA
    ).json()
    spec = shown["spec"]
    assert spec["quantity"] == 1
    assert spec["fulfillment_line_item_id"].startswith(
        "gid://shopify/FulfillmentLineItem/"
    )
    assert spec["policy_version"] == 3


async def decision(api, proposal_id, who, digest=None):
    if digest is None:
        digest = api.get(
            f"/proposals/{proposal_id}", headers=LEENA
        ).json()["spec_digest"]
    return api.post(
        f"/proposals/{proposal_id}/decision",
        json={
            "decision": "approved",
            "spec_digest": digest,
        },
        headers=who,
    )


async def test_approval_queues_one_operation(
    as_mira, api
):
    pid = (await propose(as_mira))["proposal_id"]
    first = await decision(api, pid, LEENA)
    again = await decision(api, pid, LEENA)
    assert first.json()["state"] == "ready"
    assert (
        again.json()["detail"] == "proposal_not_pending"
    )


async def test_requester_cannot_approve(as_mira, api):
    pid = (await propose(as_mira))["proposal_id"]
    response = await decision(api, pid, MIRA)
    assert response.json()["detail"] == (
        "second_person_required"
    )


async def test_changed_proposal_is_refused(as_mira, api):
    pid = (await propose(as_mira))["proposal_id"]
    response = await decision(api, pid, LEENA, "0" * 64)
    assert response.json()["detail"] == "proposal_changed"


async def test_other_store_cannot_see_or_approve(
    as_mira, api
):
    pid = (await propose(as_mira))["proposal_id"]
    seen = api.get(f"/proposals/{pid}", headers=ANA)
    assert seen.status_code == 404
    response = await decision(api, pid, ANA)
    assert response.json()["detail"] == (
        "approver_store_denied"
    )


async def test_expired_proposal_is_refused(
    as_mira, api, db
):
    pid = (await propose(as_mira))["proposal_id"]
    db.execute(
        "UPDATE proposals SET expires_at = now() "
        "WHERE id = %s",
        (pid,),
    )
    db.commit()
    response = await decision(api, pid, LEENA)
    assert response.json()["detail"] == "proposal_expired"


async def test_one_live_return_per_case(as_mira, api):
    first = (await propose(as_mira))["proposal_id"]
    second = (await propose(as_mira))["proposal_id"]
    await decision(api, first, LEENA)
    response = await decision(api, second, LEENA)
    assert response.json()["detail"] == (
        "return_already_in_progress"
    )


async def test_escalation_has_a_fixed_channel(as_mira):
    result = await as_mira.call_tool(
        "propose_escalation",
        {
            "case_id": "CASE-17",
            "summary": "Cracked screen <!here>",
        },
    )
    assert "&lt;!here&gt;" in result.data["preview"]
    with pytest.raises(Exception):
        await as_mira.call_tool(
            "propose_escalation",
            {
                "case_id": "CASE-17",
                "summary": "x",
                "channel": "C-GENERAL",
            },
        )


async def test_writes_can_be_paused(as_mira, monkeypatch):
    monkeypatch.setenv("SECONDLOOP_WRITES", "off")
    data = await propose(as_mira)
    assert data["code"] == "writes_paused"
