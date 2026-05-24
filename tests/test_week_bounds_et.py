"""Wave 0 RED stub — ET week-boundary semantics (REQ-OPS-01, D-B6b).

These tests are expected to FAIL until Plan 05-06 implements
``pipeline.week.week_bounds_et`` and ``active_digest_week_id`` per
05-CONTEXT.md D-B6b ("Sunday 00:00 ET through Saturday 23:59 ET").

Acceptance criterion (see ``05-VALIDATION.md`` Wave 0):
- Covers ET Sun-Sat week semantics, DST boundary cases, and the
  Saturday-ending ISO week_id mapping rule from 05-RESEARCH.md.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

ET = ZoneInfo("America/New_York")


def test_week_bounds_et_function_is_implemented() -> None:
    """Plan 05-06 must export ``week_bounds_et`` from ``pipeline.week``."""
    pytest.importorskip("pipeline.week")
    from pipeline import week as week_mod

    assert hasattr(week_mod, "week_bounds_et"), (
        "Plan 05-06 must add pipeline.week.week_bounds_et "
        "(Sun 00:00 ET – Sat 23:59 ET window per D-B6b)"
    )


def test_active_digest_week_id_function_is_implemented() -> None:
    """Plan 05-06 must export ``active_digest_week_id`` from ``pipeline.week``."""
    pytest.importorskip("pipeline.week")
    from pipeline import week as week_mod

    assert hasattr(week_mod, "active_digest_week_id"), (
        "Plan 05-06 must add pipeline.week.active_digest_week_id "
        "(returns the prior Sun-Sat ET week for a given moment per D-B6b)"
    )


def test_week_bounds_et_sun_to_sat_window() -> None:
    """ET week bounds for 2026-W21 (Sat-end mapping): Sun 2026-05-17 00:00 ET → Sat 2026-05-23 23:59 ET."""
    from pipeline.week import week_bounds_et  # noqa: PLC0415 — RED stub

    start, end = week_bounds_et("2026-W21")
    assert start == datetime(2026, 5, 17, 0, 0, 0, tzinfo=ET)
    assert end == datetime(2026, 5, 23, 23, 59, 59, tzinfo=ET)


def test_active_digest_week_id_sunday_morning_resolves_to_prior_week() -> None:
    """Sun 05:00 ET on 2026-05-24 resolves to the prior Sun-Sat ET window → 2026-W21."""
    from pipeline.week import active_digest_week_id  # noqa: PLC0415 — RED stub

    sunday_morning = datetime(2026, 5, 24, 5, 0, 0, tzinfo=ET)
    assert active_digest_week_id(sunday_morning) == "2026-W21"


def test_week_bounds_et_dst_boundary_spring_forward() -> None:
    """ET window crossing DST spring-forward (2nd Sun of March) stays 7 ET days end-to-end."""
    from pipeline.week import week_bounds_et  # noqa: PLC0415 — RED stub

    start, end = week_bounds_et("2026-W10")
    delta_days = (end.date() - start.date()).days
    assert delta_days == 6, "Sun→Sat is 6 calendar-day delta regardless of DST"
