"""ISO week boundary tests (D-10 UTC)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pipeline.week import current_week_id, parse_week_id, week_bounds


def test_current_week_id_format() -> None:
    week_id = current_week_id()
    assert len(week_id) == 8 and week_id[4:6] == "-W"
    parse_week_id(week_id)


def test_week_bounds_monday_to_monday() -> None:
    """Week 19 of 2026 starts Mon 2026-05-04 00:00 UTC and ends 2026-05-11 00:00 UTC."""
    start, end = week_bounds("2026-W19")
    assert start == datetime(2026, 5, 4, tzinfo=UTC)
    assert end == datetime(2026, 5, 11, tzinfo=UTC)


def test_invalid_week_id_raises() -> None:
    with pytest.raises(ValueError):
        parse_week_id("2026-WK19")
    with pytest.raises(ValueError):
        parse_week_id("2026-W00")
    with pytest.raises(ValueError):
        parse_week_id("2026-W54")


def test_iso_week_53_supported() -> None:
    """2020 had 53 ISO weeks — week 53 starts Mon 2020-12-28 UTC."""
    start, end = week_bounds("2020-W53")
    assert start == datetime(2020, 12, 28, tzinfo=UTC)
    assert end == datetime(2021, 1, 4, tzinfo=UTC)
