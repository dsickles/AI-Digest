"""Orchestrator cascade wiring — title_changed deletes summaries (WR-01)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from pipeline.cascade import STAGE_DEDUP
from pipeline.config import RssSource
from pipeline.models import NormalizedItem
from pipeline.orchestrator import _apply_cascade_for_item
from store.db import (
    connect,
    get_existing_summary,
    insert_item_summary,
    upsert_item,
    upsert_source,
)


def test_apply_cascade_title_only_deletes_summary(apply_schema: Path) -> None:
    """Title-only RSS edits invalidate item_summaries via STAGE_SUMMARIZE."""
    db_path = apply_schema
    week_id = "2026-W21"
    source = RssSource(
        id="cascade-source",
        type="rss",
        url="https://example.com/feed",
        display_name="Cascade Source",
        tag="technical",
        enabled=True,
    )
    item = NormalizedItem.build(
        source_id=source.id,
        external_id="ext-cascade",
        canonical_url="https://example.com/cascade",
        title="Breaking: AI Model Ships",
        publisher="Cascade Source",
        published_at=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
        raw_content_html="<p>" + " ".join(["word"] * 40) + "</p>",
    )
    stable_hash = item.content_hash

    with connect(db_path) as conn:
        upsert_source(conn, source)
        item_id = upsert_item(conn, item)
        insert_item_summary(
            conn,
            item_id=item_id,
            week_id=week_id,
            tldr="Old summary for unchanged body.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            summary_status="ok",
        )
        conn.commit()

        assert (
            get_existing_summary(conn, item_id, week_id, "summarize_v1") is not None
        )

        stages = _apply_cascade_for_item(
            conn,
            week_id=week_id,
            item_id=item_id,
            old_hash=stable_hash,
            new_hash=stable_hash,
            old_title="Breaking: AI Model Ships",
            new_title="UPDATED: AI Model Ships Today",
            log=MagicMock(),
        )
        conn.commit()

        assert STAGE_DEDUP in stages
        assert get_existing_summary(conn, item_id, week_id, "summarize_v1") is None
