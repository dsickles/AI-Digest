"""ISO week helpers (D-10: UTC week boundaries).

Plan 01-04 wires ``--week YYYY-Www`` through the CLI; in the skeleton the
orchestrator just calls ``current_week_id()`` once at the entry point.
``datetime.now()`` lives ONLY here — adapters and renderers receive the
resolved week_id from the orchestrator.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta

WEEK_ID_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def current_week_id(now: datetime | None = None) -> str:
    """Return the current ISO week as ``YYYY-Www`` in UTC."""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    iso_year, iso_week, _ = moment.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def parse_week_id(week_id: str) -> tuple[int, int]:
    """Split ``YYYY-Www`` into ``(year, week)``; raises ValueError on bad shape."""
    match = WEEK_ID_RE.match(week_id)
    if not match:
        raise ValueError(f"invalid ISO week id {week_id!r}; expected 'YYYY-Www'")
    year = int(match.group(1))
    week = int(match.group(2))
    if not (1 <= week <= 53):
        raise ValueError(f"week number out of range in {week_id!r}")
    return year, week


def week_bounds(week_id: str) -> tuple[datetime, datetime]:
    """Return ``(week_start, week_end)`` as tz-aware UTC datetimes.

    ``week_start`` is Monday 00:00 UTC; ``week_end`` is Monday of the next
    week 00:00 UTC (half-open interval — use with ``>= start AND < end``).
    Uses ``date.fromisocalendar`` so leap weeks (53-week years) work.
    """
    year, week = parse_week_id(week_id)
    monday = date.fromisocalendar(year, week, 1)
    week_start = datetime.combine(monday, time.min, tzinfo=UTC)
    week_end = week_start + timedelta(days=7)
    return week_start, week_end
