"""ISO week helpers (D-10: UTC week boundaries; D-B6b: ET digest windows).

Plan 01-04 wires ``--week YYYY-Www`` through the CLI; in the skeleton the
orchestrator just calls ``current_week_id()`` once at the entry point.
``datetime.now()`` lives ONLY here — adapters and renderers receive the
resolved week_id from the orchestrator.

Digest week semantics (D-B6b): the reader-facing window is Sunday 00:00
America/New_York through Saturday 23:59:59 ET. The archive ``week_id`` is
the ISO week number of the **Saturday** ending that window — e.g. a digest
published Sun 2026-05-24 covers Sun 2026-05-17 – Sat 2026-05-23 and is
stored as ``2026-W21`` (ISO week of Sat 2026-05-23).
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

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
    try:
        date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise ValueError(f"invalid ISO week id {week_id!r}") from exc
    return year, week


def prior_week_id(week_id: str) -> str:
    """Return the ISO week immediately before ``week_id`` (handles year boundaries)."""
    year, week = parse_week_id(week_id)
    monday = date.fromisocalendar(year, week, 1)
    prior_monday = monday - timedelta(days=7)
    iso_year, iso_week, _ = prior_monday.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def week_bounds(week_id: str) -> tuple[datetime, datetime]:
    """Return ``(week_start, week_end)`` as tz-aware UTC datetimes.

    ``week_start`` is Monday 00:00:00 UTC; ``week_end`` is Sunday 23:59:59 UTC
    (inclusive window for ``published_at`` filtering). Uses ``fromisocalendar``
    so leap weeks (53-week years) work.
    """
    year, week = parse_week_id(week_id)
    monday = date.fromisocalendar(year, week, 1)
    sunday = date.fromisocalendar(year, week, 7)
    week_start = datetime.combine(monday, time.min, tzinfo=UTC)
    week_end = datetime.combine(sunday, time(23, 59, 59), tzinfo=UTC)
    return week_start, week_end


def week_bounds_et(week_id: str) -> tuple[datetime, datetime]:
    """Return ``(week_start, week_end)`` as tz-aware ET datetimes.

    The digest window is Sunday 00:00:00 through Saturday 23:59:59 in
    ``America/New_York``. ``week_id`` is the ISO week of the Saturday that
    ends the window (Saturday-ending rule, D-B6b).
    """
    year, week = parse_week_id(week_id)
    saturday = date.fromisocalendar(year, week, 6)
    sunday = saturday - timedelta(days=6)
    week_start = datetime.combine(sunday, time.min, tzinfo=ET)
    week_end = datetime.combine(saturday, time(23, 59, 59), tzinfo=ET)
    return week_start, week_end


def active_digest_week_id(reference: datetime | None = None) -> str:
    """Return the ``week_id`` for the active digest week at ``reference``.

    On Sunday (e.g. the 05:00 ET cron), returns the ISO week of the Saturday
    that ended the prior Sun–Sat ET window. Mon–Sat returns the ISO week of
    the Saturday before the most recent Sunday — the week whose digest was
    (or will be) published on that Sunday.
    """
    moment = (reference or datetime.now(ET)).astimezone(ET)
    if moment.weekday() == 6:
        saturday = moment.date() - timedelta(days=1)
    else:
        days_since_sunday = (moment.weekday() + 1) % 7
        last_sunday = moment.date() - timedelta(days=days_since_sunday)
        saturday = last_sunday - timedelta(days=1)
    iso_year, iso_week, _ = saturday.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"
