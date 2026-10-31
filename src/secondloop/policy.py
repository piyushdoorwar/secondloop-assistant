"""Apply the damage-return policy to one order line."""

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

Outcome = Literal[
    "eligible_for_proposal",
    "outside_window",
    "no_delivery_record",
    "return_already_open",
    "report_before_delivery",
]


class Assessment(BaseModel):
    outcome: Outcome
    policy_version: int
    window_days: int
    timezone: str
    delivered_on: str | None
    reported_on: str
    days_after_delivery: int | None


def local_date(instant: str, tz: ZoneInfo):
    moment = datetime.fromisoformat(instant)
    return moment.astimezone(tz).date()


def assess(
    policy, line, open_returns, reported_at, timezone
) -> Assessment:
    tz = ZoneInfo(timezone)
    reported = local_date(reported_at, tz)
    base = {
        "policy_version": policy["version"],
        "window_days": policy["window_days"],
        "timezone": timezone,
        "reported_on": reported.isoformat(),
    }
    if line.delivered_at is None:
        delivered, days = None, None
    else:
        delivered = local_date(line.delivered_at, tz)
        days = (reported - delivered).days
    if open_returns:
        outcome = "return_already_open"
    elif days is None:
        outcome = "no_delivery_record"
    elif days < 0:
        outcome = "report_before_delivery"
    elif days > policy["window_days"]:
        outcome = "outside_window"
    else:
        outcome = "eligible_for_proposal"
    return Assessment(
        outcome=outcome,
        delivered_on=(
            delivered.isoformat() if delivered else None
        ),
        days_after_delivery=days,
        **base,
    )
