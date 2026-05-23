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


def _insert_orphan_rank(conn, *, week_id: str, cluster_id: str) -> None:
    """Simulate stale rank rows left after a partial dedup invalidation (FK bypass)."""
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        """
        INSERT INTO cluster_ranks (
            cluster_rank_id, cluster_id, week_id, rank_score, rank_position,
            rank_status, prompt_version, model_id
        ) VALUES (?, ?, ?, 50.0, 1, 'ok', ?, 'gemini-2.5-flash')
        """,
        (f"rank-{cluster_id}", cluster_id, week_id, PROMPT_VERSION),
    )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def _seed_cluster_with_summary(conn, *, week_id: str) -> None:
    _seed_source_and_item(conn)
    insert_story_cluster(
        conn,
        cluster_id="cluster-1",
        week_id=week_id,
        canonical_item_id="item-1",
        canonical_url="https://example.com/a",
        title_normalized="title",
    )
    insert_cluster_summary(
        conn,
        cluster_id="cluster-1",
        week_id=week_id,
        category="technical",
        category_confidence="high",
        category_status="ok",
        prompt_version="categorize_v1",
        model_id="gemini-2.5-flash-lite",
    )


def test_rank_week_reruns_when_cluster_ranks_do_not_join_clusters(
    apply_schema: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-02: stale orphan rank rows must not skip the rank LLM path."""
    from pipeline.llm.rank import ClusterRankResult

    week_id = "2026-W21"
    called = {"rank": False}

    def _fake_rank(**kwargs: object) -> list[ClusterRankResult]:
        called["rank"] = True
        clusters = kwargs.get("clusters", [])
        return [
            ClusterRankResult(
                cluster_id=c.cluster_id,
                rank_score=90.0,
                rank_position=i + 1,
                rank_status="ok",
                prompt_version=PROMPT_VERSION,
                model_id="gemini-2.5-flash",
            )
            for i, c in enumerate(clusters)
        ]

    monkeypatch.setattr("pipeline.llm.rank.rank_week_clusters", _fake_rank)

    with connect(apply_schema) as conn:
        _seed_cluster_with_summary(conn, week_id=week_id)
        _insert_orphan_rank(conn, week_id=week_id, cluster_id="cluster-stale")
        log = structlog.get_logger("test")
        _rank_week(
            week_id=week_id,
            conn=conn,
            log=log,
            stats=RunStats(week_id=week_id),
        )

    assert called["rank"] is True


def test_rollup_week_reruns_when_ranks_stale_and_weekly_rollup_exists(
    apply_schema: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-02: existing weekly rollup must not skip when ranks fail coverage check."""
    from pipeline.llm.rollup import (
        CATEGORY_PROMPT_VERSION,
        RollupResult,
        WEEKLY_PROMPT_VERSION,
    )

    week_id = "2026-W21"
    called = {"weekly": False}

    def _fake_weekly(**kwargs: object) -> RollupResult:
        called["weekly"] = True
        return RollupResult(
            narrative_md="Fresh weekly narrative.",
            rollup_status="ok",
            prompt_version=WEEKLY_PROMPT_VERSION,
            model_id="gemini-2.5-flash",
        )

    monkeypatch.setattr("pipeline.llm.rollup.rollup_weekly", _fake_weekly)
    monkeypatch.setattr(
        "pipeline.llm.rollup.rollup_category",
        lambda **kw: RollupResult(
            narrative_md="Mini",
            rollup_status="ok",
            prompt_version=CATEGORY_PROMPT_VERSION,
            model_id="gemini-2.5-flash",
        ),
    )

    with connect(apply_schema) as conn:
        _seed_cluster_with_summary(conn, week_id=week_id)
        _insert_orphan_rank(conn, week_id=week_id, cluster_id="cluster-stale")
        insert_weekly_rollup(
            conn,
            week_id=week_id,
            scope="weekly",
            narrative_md="Stale weekly narrative.",
            rollup_status="ok",
            prompt_version=WEEKLY_PROMPT_VERSION,
            model_id="gemini-2.5-flash",
        )
        conn.commit()
        log = structlog.get_logger("test")
        _rollup_week(
            week_id=week_id,
            conn=conn,
            log=log,
            stats=RunStats(week_id=week_id),
        )

    assert called["weekly"] is True

