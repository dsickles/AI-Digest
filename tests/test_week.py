"""ISO week boundary tests (D-10 UTC)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pipeline.week import current_week_id, parse_week_id, week_bounds


def test_current_week_id_format() -> None:
    week_id = current_week_id()
    assert len(week_id) == 8 and week_id[4:6] == "-W"
    parse_week_id(week_id)


def test_week_bounds_monday_to_sunday() -> None:
    """Week 19 of 2026: Mon 2026-05-04 00:00 UTC through Sun 2026-05-10 23:59:59 UTC."""
    start, end = week_bounds("2026-W19")
    assert start == datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)
    assert end == datetime(2026, 5, 10, 23, 59, 59, tzinfo=UTC)


def test_week_bounds_2026_w19_exact() -> None:
    """Spec assertion: ISO week 19 of 2026 starts Monday 2026-05-04 UTC."""
    start, end = week_bounds("2026-W19")
    assert start.isoformat() == "2026-05-04T00:00:00+00:00"
    assert end.isoformat() == "2026-05-10T23:59:59+00:00"


def test_invalid_week_id_raises() -> None:
    with pytest.raises(ValueError):
        parse_week_id("2026-WK19")
    with pytest.raises(ValueError):
        parse_week_id("2026-W00")
    with pytest.raises(ValueError):
        parse_week_id("2026-W54")
    with pytest.raises(ValueError):
        parse_week_id("2021-W53")  # 2021 has only 52 ISO weeks


def test_iso_week_53_supported() -> None:
    """2020 had 53 ISO weeks — week 53 starts Mon 2020-12-28 UTC."""
    start, end = week_bounds("2020-W53")
    assert start == datetime(2020, 12, 28, 0, 0, 0, tzinfo=UTC)
    assert end == datetime(2021, 1, 3, 23, 59, 59, tzinfo=UTC)
