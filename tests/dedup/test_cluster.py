"""Integration tests for the clustering engine."""
from __future__ import annotations

from datetime import UTC, datetime

import structlog

from pipeline.config import RssSource
from pipeline.dedup.cluster import run_dedup_for_week
from pipeline.models import NormalizedItem
from pipeline.orchestrator import RunStats
from store.db import (
    connect,
    delete_clusters_for_week,
    get_cluster_members,
    get_clusters_for_week,
    insert_cluster_member,
    insert_cluster_ranks_batch,
    insert_cluster_summary,
    insert_story_cluster,
    insert_weekly_rollup,
    upsert_item,
    upsert_source,
)


def _seed_source(conn, source_id: str = "src-a") -> None:
    upsert_source(
        conn,
        RssSource(
            id=source_id,
            type="rss",
            url="https://example.com/feed",
            display_name="Source A",
            tag="technical",
            enabled=True,
        ),
    )


def _insert_item(
    conn,
    *,
    external_id: str,
    url: str,
    title: str,
    raw_content: str,
    source_id: str = "src-a",
    published_at: datetime | None = None,
) -> str:
    item = NormalizedItem.build(
        source_id=source_id,
        external_id=external_id,
        canonical_url=url,
        title=title,
        publisher="Source A",
        published_at=published_at or datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC),
        raw_content_html=f"<p>{raw_content}</p>",
    )
    return upsert_item(conn, item)


def test_same_canonical_url_produces_one_cluster(apply_schema) -> None:
    week_id = "2026-W21"
    log = structlog.get_logger()
    stats = RunStats(week_id=week_id, phase="dedup")

    with connect(apply_schema) as conn:
        _seed_source(conn)
        _insert_item(
            conn,
            external_id="a1",
            url="https://example.com/story?utm_source=x",
            title="Story headline one",
            raw_content=" ".join(["alpha"] * 20),
        )
        _seed_source(conn, "src-b")
        upsert_source(
            conn,
            RssSource(
                id="src-b",
                type="rss",
                url="https://other.example/feed",
                display_name="Source B",
                tag="technical",
                enabled=True,
            ),
        )
        _insert_item(
            conn,
            external_id="b1",
            url="https://www.example.com/story",
            title="Different title entirely",
            raw_content=" ".join(["beta"] * 10),
            source_id="src-b",
        )
        conn.commit()

        clusters_created = run_dedup_for_week(
            week_id=week_id,
            conn=conn,
            log=log,
            stats=stats,
            fetch_redirects=False,
        )

        clusters = get_clusters_for_week(conn, week_id)
        assert clusters_created == 1
        assert len(clusters) == 1
        members = get_cluster_members(conn, clusters[0]["cluster_id"])
        assert len(members) == 2


def test_fuzzy_title_merge(apply_schema) -> None:
    from tests.dedup.conftest import MATCHING_TITLE_A, MATCHING_TITLE_B

    week_id = "2026-W21"
    log = structlog.get_logger()
    stats = RunStats(week_id=week_id, phase="dedup")

    with connect(apply_schema) as conn:
        _seed_source(conn)
        _insert_item(
            conn,
            external_id="f1",
            url="https://example.com/a",
            title=MATCHING_TITLE_A,
            raw_content=" ".join(["longer"] * 30),
        )
        _insert_item(
            conn,
            external_id="f2",
            url="https://example.com/b",
            title=MATCHING_TITLE_B,
            raw_content=" ".join(["short"] * 5),
        )
        conn.commit()

        run_dedup_for_week(
            week_id=week_id,
            conn=conn,
            log=log,
            stats=stats,
            fetch_redirects=False,
        )

        clusters = get_clusters_for_week(conn, week_id)
        assert len(clusters) == 1
        assert clusters[0]["canonical_item_id"] == conn.execute(
            "SELECT item_id FROM items WHERE external_id = 'f1'"
        ).fetchone()[0]


def test_delete_clusters_for_week_clears_artifact_tables(apply_schema) -> None:
    """FK-safe rebuild: ranks/summaries/rollups removed before story_clusters (CR-01)."""
    week_id = "2026-W21"
    cluster_id = "cluster-artifact-test"

    with connect(apply_schema) as conn:
        _seed_source(conn)
        item_id = _insert_item(
            conn,
            external_id="del-1",
            url="https://example.com/del",
            title="Delete artifact test",
            raw_content=" ".join(["content"] * 20),
        )
        insert_story_cluster(
            conn,
            cluster_id=cluster_id,
            week_id=week_id,
            canonical_item_id=item_id,
            canonical_url="https://example.com/del",
            title_normalized="delete artifact test",
        )
        insert_cluster_member(
            conn,
            cluster_id=cluster_id,
            item_id=item_id,
            is_canonical=True,
        )
        insert_cluster_summary(
            conn,
            cluster_id=cluster_id,
            week_id=week_id,
            category="technical",
            category_confidence="high",
            category_status="ok",
            prompt_version="categorize_v1",
            model_id="gemini-2.5-flash-lite",
        )
        insert_cluster_ranks_batch(
            conn,
            week_id=week_id,
            rows=[
                {
                    "cluster_id": cluster_id,
                    "rank_score": 90.0,
                    "rank_position": 1,
                    "rank_status": "ok",
                    "prompt_version": "rank_v1",
                    "model_id": "gemini-2.5-flash-lite",
                }
            ],
        )
        insert_weekly_rollup(
            conn,
            week_id=week_id,
            scope="weekly",
            narrative_md="Weekly narrative",
            rollup_status="ok",
            prompt_version="rollup_weekly_v1",
            model_id="gemini-2.5-flash",
        )
        conn.commit()

        delete_clusters_for_week(conn, week_id)
        conn.commit()

        for table in ("cluster_ranks", "cluster_summaries", "weekly_rollups", "story_clusters"):
            count = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE week_id = ?",
                (week_id,),
            ).fetchone()["n"]
            assert count == 0, f"{table} still has rows for {week_id}"

        member_count = conn.execute(
            """
            SELECT COUNT(*) AS n
              FROM cluster_members
             WHERE cluster_id = ?
            """,
            (cluster_id,),
        ).fetchone()["n"]
        assert member_count == 0
