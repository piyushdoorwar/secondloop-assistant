"""Trusted links from support cases to vendor records."""

import json
import pathlib

from pydantic import BaseModel

DATA = pathlib.Path(__file__).parents[2] / "data"


class Case(BaseModel):
    case_id: str
    store_id: str
    shop: str
    order_id: str
    order_ref: str


def load_cases(
    path=DATA / "cases.json",
) -> dict[str, Case]:
    rows = json.loads(pathlib.Path(path).read_text())
    return {r["case_id"]: Case(**r) for r in rows}
