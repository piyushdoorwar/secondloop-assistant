"""Trusted links from support cases to vendor records."""

import json
import pathlib

from pydantic import BaseModel

from secondloop.paths import DATA


class Case(BaseModel):
    case_id: str
    store_id: str
    shop: str
    order_id: str | None
    order_ref: str | None
    customer_id: str | None = None
    reported_at: str | None = None


def load_cases(
    path=DATA / "cases.json",
) -> dict[str, Case]:
    rows = json.loads(pathlib.Path(path).read_text())
    return {r["case_id"]: Case(**r) for r in rows}
