"""Smoke + idempotence tests for the SQLite store."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pipeline.config import RssSource
from pipeline.models import NormalizedItem
from store.db import connect, upsert_item, upsert_source


def _make_source() -> RssSource:
    return RssSource(
        id="test-source",
        type="rss",
        url="https://example.com/feed",
        display_name="Test Source",
        tag="technical",
        enabled=True,
    )


def _make_item(*, external_id: str = "ext-1", title: str = "Hello World") -> NormalizedItem:
    return NormalizedItem.build(
        source_id="test-source",
        external_id=external_id,
        canonical_url="https://example.com/post-1",
        title=title,
        publisher="Test Source",
        published_at=datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC),
        raw_content_html="<p>body <b>text</b></p>",
    )


def test_apply_schema_creates_items_table(apply_schema: Path) -> None:
    """init_db should create all four tables on a fresh SQLite file."""
    expected = {"sources", "items", "item_summaries", "pipeline_runs"}
    with sqlite3.connect(apply_schema) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    actual = {r[0] for r in rows}
    assert expected.issubset(actual), f"missing tables: {expected - actual}"


def test_upsert_idempotent(apply_schema: Path) -> None:
    """Re-upserting the same (source_id, external_id) keeps a single row (INGEST-08)."""
    source = _make_source()
    item = _make_item()

    with connect(apply_schema) as conn:
        upsert_source(conn, source)
        first_id = upsert_item(conn, item)
        second_id = upsert_item(conn, item)
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM items WHERE source_id = ? AND external_id = ?",
            (item.source_id, item.external_id),
        ).fetchone()[0]

    assert first_id == second_id, "upsert must preserve item_id on conflict"
    assert count == 1, f"expected 1 item after duplicate upsert, got {count}"


def test_upsert_item_is_idempotent(apply_schema: Path) -> None:
    """Re-upserting the same (source_id, external_id) returns the same item_id."""
    source = _make_source()
    item = _make_item()

    with connect(apply_schema) as conn:
        upsert_source(conn, source)
        first_id = upsert_item(conn, item)
        second_id = upsert_item(conn, item)
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    assert first_id == second_id, "upsert must preserve item_id on conflict"
    assert count == 1, f"expected 1 item after duplicate upsert, got {count}"


def test_upsert_item_updates_mutable_fields(apply_schema: Path) -> None:
    """A second upsert should overwrite title/raw_content while keeping item_id."""
    source = _make_source()
    initial = _make_item(title="Original Title")
    edited = _make_item(title="Edited Title")

    with connect(apply_schema) as conn:
        upsert_source(conn, source)
        item_id_before = upsert_item(conn, initial)
        item_id_after = upsert_item(conn, edited)
        conn.commit()
        row = conn.execute(
            "SELECT title FROM items WHERE item_id = ?", (item_id_after,)
        ).fetchone()

    assert item_id_before == item_id_after
    assert row["title"] == "Edited Title"


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_phase2_schema_migration(temp_sqlite_path: Path) -> None:
    """Phase 2 additive columns land on fresh + re-applied init_db (D-23, D-28, D-40)."""
    from store.db import init_db

    init_db(temp_sqlite_path)
    init_db(temp_sqlite_path)

    with connect(temp_sqlite_path) as conn:
        items_cols = _column_names(conn, "items")
        sources_cols = _column_names(conn, "sources")
        summaries_cols = _column_names(conn, "item_summaries")

    assert "transcript_status" in items_cols, "D-23: items.transcript_status missing"
    assert "summary_input_truncated" in summaries_cols, "D-28: item_summaries.summary_input_truncated missing"
    assert "last_success_at" in sources_cols, "D-40: sources.last_success_at missing"
    assert "last_item_at" in sources_cols, "D-40: sources.last_item_at missing"
    assert "last_error_category" in sources_cols, "D-40: sources.last_error_category missing"
