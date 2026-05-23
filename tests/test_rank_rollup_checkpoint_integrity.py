"""Rank/rollup checkpoint integrity — CR-02 stale skip regression tests."""
from __future__ import annotations

from pathlib import Path

import pytest
import structlog

from pipeline.llm.rank import PROMPT_VERSION
from pipeline.orchestrator import RunStats, _rank_week, _rollup_week
from store.db import (
    connect,
    insert_cluster_ranks_batch,
    insert_cluster_summary,
    insert_story_cluster,
    insert_weekly_rollup,
    ranks_cover_current_clusters,
)


def _seed_source_and_item(conn, *, item_id: str = "item-1") -> None:
    conn.execute(
        """
        INSERT INTO sources (source_id, type, url, display_name)
        VALUES ('src-1', 'rss', 'https://example.com/feed', 'Test')
        """
    )
    conn.execute(
        """
        INSERT INTO items (
            item_id, source_id, external_id, canonical_url, title,
            publisher, published_at, raw_content, content_hash
        ) VALUES (
            ?, 'src-1', 'ext-1', 'https://example.com/a',
            'Title', 'Test', '2026-05-20T12:00:00Z', 'body', 'hash'
        )
        """,
        (item_id,),
    )


def test_ranks_cover_matching_clusters_and_ranks_returns_true(apply_schema: Path) -> None:
    week_id = "2026-W21"
    with connect(apply_schema) as conn:
        _seed_source_and_item(conn)
        insert_story_cluster(
            conn,
            cluster_id="cluster-1",
            week_id=week_id,
            canonical_item_id="item-1",
            canonical_url="https://example.com/a",
            title_normalized="title",
        )
        insert_cluster_ranks_batch(
            conn,
            week_id=week_id,
            rows=[
                {
                    "cluster_id": "cluster-1",
                    "rank_score": 50.0,
                    "rank_position": 1,
                    "rank_status": "ok",
                    "prompt_version": PROMPT_VERSION,
                    "model_id": "gemini-2.5-flash",
                }
            ],
        )
        conn.commit()
        assert ranks_cover_current_clusters(conn, week_id, PROMPT_VERSION) is True


def test_ranks_cover_orphan_cluster_id_returns_false(apply_schema: Path) -> None:
    week_id = "2026-W21"
    with connect(apply_schema) as conn:
        _seed_source_and_item(conn)
        insert_story_cluster(
            conn,
            cluster_id="cluster-1",
            week_id=week_id,
            canonical_item_id="item-1",
            canonical_url="https://example.com/a",
            title_normalized="title",
        )
        insert_cluster_ranks_batch(
            conn,
            week_id=week_id,
            rows=[
                {
                    "cluster_id": "cluster-1",
                    "rank_score": 50.0,
                    "rank_position": 1,
                    "rank_status": "ok",
                    "prompt_version": PROMPT_VERSION,
                    "model_id": "gemini-2.5-flash",
                }
            ],
        )
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DELETE FROM story_clusters WHERE cluster_id = ?", ("cluster-1",))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        assert ranks_cover_current_clusters(conn, week_id, PROMPT_VERSION) is False


def test_ranks_cover_empty_clusters_and_ranks_returns_true(apply_schema: Path) -> None:
    week_id = "2026-W21"
    with connect(apply_schema) as conn:
        assert ranks_cover_current_clusters(conn, week_id, PROMPT_VERSION) is True

