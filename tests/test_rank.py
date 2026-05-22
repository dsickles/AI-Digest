"""Rank stage unit tests — mocked Gemini client."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from pipeline.llm.rank import (
    MODEL_ID,
    PROMPT_VERSION,
    ClusterRankInput,
    RankResponse,
    RankScoreEntry,
    rank_week_clusters,
)
from store.db import (
    connect,
    get_ranks_for_week,
    init_db,
    insert_cluster_ranks_batch,
    insert_story_cluster,
)


def _cluster(
    *,
    cluster_id: str,
    title: str,
    published_at: datetime,
    category: str = "technical",
    summary: str = "Summary text.",
) -> ClusterRankInput:
    return ClusterRankInput(
        cluster_id=cluster_id,
        category=category,
        title=title,
        summary_text=summary,
        published_at=published_at,
    )


def _mock_response(rankings: list[tuple[str, float]]) -> MagicMock:
    response = MagicMock()
    response.parsed = RankResponse(
        rankings=[
            RankScoreEntry(cluster_id=cid, rank_score=score)
            for cid, score in rankings
        ]
    )
    usage = MagicMock()
    usage.prompt_token_count = 200
    usage.candidates_token_count = 80
    response.usage_metadata = usage
    return response


def _mock_client(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def test_happy_path_highest_score_gets_rank_position_one() -> None:
    clusters = [
        _cluster(
            cluster_id="c-low",
            title="Minor update",
            published_at=datetime(2026, 5, 22, tzinfo=UTC),
        ),
        _cluster(
            cluster_id="c-high",
            title="Major launch",
            published_at=datetime(2026, 5, 20, tzinfo=UTC),
        ),
    ]
    response = _mock_response([("c-low", 10.0), ("c-high", 95.0)])
    results = rank_week_clusters(
        week_id="2026-W21",
        clusters=clusters,
        client=_mock_client(response),
    )
    by_id = {r.cluster_id: r for r in results}
    assert by_id["c-high"].rank_position == 1
    assert by_id["c-low"].rank_position == 2
    assert by_id["c-high"].rank_status == "ok"
    assert by_id["c-high"].prompt_version == PROMPT_VERSION
    assert by_id["c-high"].model_id == MODEL_ID


def test_api_error_falls_back_to_published_at_descending() -> None:
    clusters = [
        _cluster(
            cluster_id="c-old",
            title="Older story",
            published_at=datetime(2026, 5, 18, tzinfo=UTC),
        ),
        _cluster(
            cluster_id="c-new",
            title="Newer story",
            published_at=datetime(2026, 5, 22, tzinfo=UTC),
        ),
    ]
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("503 unavailable")

    results = rank_week_clusters(
        week_id="2026-W21",
        clusters=clusters,
        client=client,
    )
    by_id = {r.cluster_id: r for r in results}
    assert by_id["c-new"].rank_position == 1
    assert by_id["c-old"].rank_position == 2
    assert by_id["c-new"].rank_status == "api_error"


def test_classify_llm_exception_import_present() -> None:
    import inspect

    from pipeline.llm import rank as rank_mod

    source = inspect.getsource(rank_mod)
    assert "from pipeline.llm.exceptions import classify_llm_exception" in source


def test_rank_skips_llm_when_rows_already_present(apply_schema, monkeypatch) -> None:
    """Stage-level checkpoint skip when rank_v1 rows exist (PIPELINE-05)."""
    from pipeline.llm.rank import PROMPT_VERSION
    from pipeline.orchestrator import RunStats, _rank_week
    from store.db import connect, get_ranks_for_week, insert_cluster_ranks_batch, insert_story_cluster

    week_id = "2026-W21"
    called = {"rank": False}

    def _fake_rank(**kwargs):
        called["rank"] = True
        return []

    monkeypatch.setattr("pipeline.llm.rank.rank_week_clusters", _fake_rank)

    with connect(apply_schema) as conn:
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
                'item-1', 'src-1', 'ext-1', 'https://example.com/a',
                'Title', 'Test', '2026-05-20T12:00:00Z', 'body', 'hash'
            )
            """
        )
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

        stats = RunStats(week_id=week_id)
        import structlog

        log = structlog.get_logger("test")
        _rank_week(week_id=week_id, conn=conn, log=log, stats=stats)

        assert called["rank"] is False
        rows = get_ranks_for_week(conn, week_id, PROMPT_VERSION)
        assert len(rows) == 1


def test_insert_cluster_ranks_batch_persists_position_one(apply_schema) -> None:
    week_id = "2026-W21"
    with connect(apply_schema) as conn:
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
                'item-1', 'src-1', 'ext-1', 'https://example.com/a',
                'Title', 'Test', '2026-05-20T12:00:00Z', 'body', 'hash'
            )
            """
        )
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
                    "rank_score": 88.0,
                    "rank_position": 1,
                    "rank_status": "ok",
                    "prompt_version": PROMPT_VERSION,
                    "model_id": MODEL_ID,
                }
            ],
        )
        conn.commit()
        rows = get_ranks_for_week(conn, week_id, PROMPT_VERSION)
    assert len(rows) == 1
    assert rows[0]["rank_position"] == 1
    assert rows[0]["model_id"] == MODEL_ID
