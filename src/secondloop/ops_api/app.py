"""SecondLoop's operations service (chapter 4).

The warehouse and support tools already use this API.
State is in memory here; chapter 9 moves it to
PostgreSQL.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="SecondLoop operations", version="1.4.0"
)

POLICIES = {
    2: {
        "policy_id": "damage",
        "version": 2,
        "effective_on": "2026-03-01",
        "window_days": 14,
        "window_starts": "delivery",
        "approval_required": True,
        "text": (
            "Items that arrive damaged may be returned "
            "within 14 days of delivery."
        ),
    },
    3: {
        "policy_id": "damage",
        "version": 3,
        "effective_on": "2026-10-01",
        "window_days": 30,
        "window_starts": "delivery",
        "approval_required": True,
        "text": (
            "Items that arrive damaged may be returned "
            "within 30 calendar days of delivery, "
            "counted in the store's time zone. A "
            "replacement needs approval from a second "
            "employee. Available stock is not a "
            "reservation."
        ),
    },
}
CURRENT_POLICY = 3
STOCK = {"LAP-14-R": 2, "CHG-65-C": 40, "HDP-BT-R": 6}
RESERVED: dict[str, list[str]] = {}
REPLACEMENTS: dict[str, dict] = {}


class ReplacementIn(BaseModel):
    case_id: str = Field(pattern=r"^CASE-\d{1,8}$")
    sku: str
    quantity: int = Field(ge=1, le=5)


class Reservation(BaseModel):
    case_id: str = Field(pattern=r"^CASE-\d{1,8}$")


@app.get(
    "/policies/damage",
    operation_id="current_damage_policy",
)
def current_damage_policy():
    """Which damage policy version is in force."""
    return {
        "policy_id": "damage",
        "version": CURRENT_POLICY,
    }


@app.get(
    "/policies/damage/{version}",
    operation_id="damage_policy_version",
)
def damage_policy_version(version: int):
    """One version of the damage-return policy."""
    if version not in POLICIES:
        raise HTTPException(404, "Unknown policy version")
    return POLICIES[version]


@app.get("/stock/{sku}", operation_id="warehouse_stock")
def warehouse_stock(sku: str, case_id: str | None = None):
    """Units on hand and units already reserved.

    With case_id, also says whether a unit is held for
    that case.
    """
    if sku not in STOCK:
        raise HTTPException(404, "Unknown SKU")
    holders = RESERVED.get(sku, [])
    result = {
        "sku": sku,
        "on_hand": STOCK[sku],
        "reserved": len(holders),
        "available": STOCK[sku] - len(holders),
    }
    if case_id is not None:
        result["held_for_case"] = case_id in holders
    return result


@app.post(
    "/stock/{sku}/reservations",
    operation_id="reserve_stock",
    status_code=201,
)
def reserve_stock(sku: str, body: Reservation):
    """Hold one unit for a case."""
    stock = warehouse_stock(sku)
    if stock["available"] < 1:
        raise HTTPException(409, "No unit available")
    RESERVED.setdefault(sku, []).append(body.case_id)
    return {"sku": sku, "case_id": body.case_id}


@app.get(
    "/replacements", operation_id="list_replacements"
)
def list_replacements(case_id: str):
    """Replacement requests for one case."""
    return [
        r
        for r in REPLACEMENTS.values()
        if r["case_id"] == case_id
    ]


@app.post(
    "/replacements",
    operation_id="create_replacement",
    status_code=201,
)
def create_replacement(body: ReplacementIn):
    """Ask the warehouse to ship a replacement."""
    if any(
        r["case_id"] == body.case_id
        and r["state"] != "cancelled"
        for r in REPLACEMENTS.values()
    ):
        raise HTTPException(
            409, "Case already has a replacement"
        )
    request_id = f"RPL-{uuid4().hex[:8]}"
    REPLACEMENTS[request_id] = {
        "request_id": request_id,
        **body.model_dump(),
        "state": "requested",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }
    return REPLACEMENTS[request_id]


@app.get(
    "/internal/diagnostics",
    operation_id="internal_diagnostics",
)
def internal_diagnostics():
    """Worker queue depth and cache state."""
    return {"queue": "replacements", "depth": 0}


@app.post(
    "/internal/cache/flush",
    operation_id="flush_cache",
)
def flush_cache():
    """Drop cached policy and stock data."""
    return {"flushed": True}
