"""Regression: SummaryResult must preserve summary_status when reconstructed
from a previously-stored item_summaries row.

Bug: prior to this fix, _summarize_week_items reconstructed SummaryResult
from a DB row without passing summary_status, so the dataclass default
("ok") was used. quota_exhausted items with empty tldr then routed to the
footer instead of the in-place degraded card per LOCKED-01.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.budget import WeekBudget
from pipeline.config import RssSource
from pipeline.models import NormalizedItem
from pipeline.orchestrator import RunStats, _summarize_week_items
from pipeline.render.html import _partition_cards, DigestCard
from store.db import (
    connect,
    init_db,
    insert_item_summary,
    upsert_item,
    upsert_source,
)


def _seed_item(conn, *, source_id: str, slug: str) -> str:
    upsert_source(
        conn,
        RssSource(
            id=source_id,
            type="rss",
            url=f"https://example.com/{source_id}.xml",
            display_name=source_id.title(),
            tag="technical",
            enabled=True,
        ),
    )
    item = NormalizedItem.build(
        source_id=source_id,
        external_id=f"ext:{slug}",
        canonical_url=f"https://example.com/{slug}",
        title=f"Test {slug}",
        publisher=source_id.title(),
        published_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
        raw_content_html="<p>Body content for the item.</p>" * 200,
    )
    return upsert_item(conn, item)


def test_existing_quota_exhausted_summary_preserves_status(tmp_path: Path) -> None:
    """When summarize stage runs again with an existing quota_exhausted row in DB,
    the SummaryResult reconstructed for the in-memory dict MUST carry summary_status
    forward (not default to 'ok'), so _partition_cards routes it to the main feed.
    """
    db = tmp_path / "test.db"
    init_db(db)
    week_id = "2026-W21"

    with connect(db) as conn:
        item_id = _seed_item(conn, source_id="src", slug="quota-item")
        insert_item_summary(
            conn,
            item_id=item_id,
            week_id=week_id,
            tldr="",
            summary_confidence="unavailable",
            prompt_version="summarize_v1",
            model_id="gemini",
            input_tokens=0,
            output_tokens=0,
            cost_usd_estimate=0.0,
            summary_status="quota_exhausted",
        )
        conn.commit()

        import structlog
        stats = RunStats(week_id=week_id, phase="summarize")
        budget = WeekBudget(cap_usd=2.0, reserved_meta_usd=0.0, baseline_per_item_usd=0.001)
        week_start = datetime(2026, 5, 18, tzinfo=UTC)
        week_end = week_start + timedelta(days=7)
        summaries = _summarize_week_items(
            week_id=week_id,
            week_start=week_start,
            week_end=week_end,
            conn=conn,
            log=structlog.get_logger("test"),
            stats=stats,
            budget=budget,
        )

    assert item_id in summaries
    assert summaries[item_id].summary_status == "quota_exhausted", (
        "summary_status from DB must propagate, not silently default to 'ok'"
    )
    assert summaries[item_id].tldr == ""


def test_partition_routes_quota_exhausted_with_empty_tldr_to_main(tmp_path: Path) -> None:
    """End-to-end: a quota_exhausted card with empty tldr must land in the main
    feed (not the footer) per LOCKED-01."""
    card = DigestCard(
        title="Test",
        publisher="Pub",
        canonical_url="https://example.com/x",
        published_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
        tldr="",
        summary_confidence="unavailable",
        source_type="rss",
        summary_status="quota_exhausted",
    )
    main_feed, also_seen = _partition_cards([card])
    assert card in main_feed
    assert card not in also_seen
