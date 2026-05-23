"""Rollup stage unit tests — mocked Gemini client."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from pipeline.llm.rollup import (
    CATEGORY_ORDER,
    CATEGORY_PROMPT_VERSION,
    WEEKLY_PROMPT_VERSION,
    ClusterRollupInput,
    RollupResult,
    rollup_category,
    rollup_weekly,
    scope_for_category,
)
from store.db import connect, get_rollups_for_week, init_db, insert_weekly_rollup


def _cluster(
    *,
    cluster_id: str,
    title: str,
    rank_position: int,
    summary: str = "Summary text.",
) -> ClusterRollupInput:
    return ClusterRollupInput(
        cluster_id=cluster_id,
        title=title,
        summary_text=summary,
        rank_position=rank_position,
    )


def _mock_prose_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    usage = MagicMock()
    usage.prompt_token_count = 400
    usage.candidates_token_count = 120
    response.usage_metadata = usage
    return response


def _mock_client(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def test_rollup_category_returns_ok_narrative() -> None:
    clusters = [
        _cluster(cluster_id="c-1", title="Launch story", rank_position=1),
        _cluster(cluster_id="c-2", title="Follow-up", rank_position=2),
    ]
    narrative = (
        "OpenAI shipped a faster inference tier on Tuesday while Anthropic "
        "matched pricing for Claude Sonnet."
    )
    result = rollup_category(
        week_id="2026-W21",
        category="technical",
        clusters=clusters,
        client=_mock_client(_mock_prose_response(narrative)),
    )
    assert result.rollup_status == "ok"
    assert result.narrative_md == narrative
    assert result.prompt_version == CATEGORY_PROMPT_VERSION


def test_rollup_weekly_uses_mini_paragraphs_only() -> None:
    minis = {
        "edtech": "School districts piloted classroom copilots.",
        "business": "Enterprise AI spend shifted to inference.",
        "technical": "New open weights models dropped mid-week.",
    }
    narrative = (
        "The week centered on inference economics and classroom pilots.\n\n"
        "Open weights and developer tooling kept pace without stealing the headline."
    )
    client = _mock_client(_mock_prose_response(narrative))
    result = rollup_weekly(
        week_id="2026-W21",
        mini_paragraphs=minis,  # type: ignore[arg-type]
        client=client,
    )
    assert result.rollup_status == "ok"
    assert result.prompt_version == WEEKLY_PROMPT_VERSION
    prompt_arg = client.models.generate_content.call_args.kwargs["contents"][0]
    assert "School districts piloted" in prompt_arg
    assert "cluster_id" not in prompt_arg


def test_api_error_sets_rollup_status() -> None:
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("503 unavailable")
    result = rollup_category(
        week_id="2026-W21",
        category="business",
        clusters=[_cluster(cluster_id="c-1", title="Story", rank_position=1)],
        client=client,
    )
    assert result.rollup_status == "api_error"
    assert result.narrative_md is None


def test_classify_llm_exception_import_present() -> None:
    import inspect

    from pipeline.llm import rollup as rollup_mod

    source = inspect.getsource(rollup_mod)
    assert "from pipeline.llm.exceptions import classify_llm_exception" in source


def test_five_rows_written_per_successful_week(apply_schema) -> None:
    """Successful hierarchical rollup persists five weekly_rollups rows."""
    week_id = "2026-W21"
    with connect(apply_schema) as conn:
        for category in CATEGORY_ORDER:
            insert_weekly_rollup(
                conn,
                week_id=week_id,
                scope=scope_for_category(category),  # type: ignore[arg-type]
                narrative_md=f"Mini for {category}.",
                rollup_status="ok",
                prompt_version=CATEGORY_PROMPT_VERSION,
                model_id="gemini-2.5-flash",
                input_token_count=100,
                output_token_count=80,
                cost_usd_estimate=0.0001,
            )
        insert_weekly_rollup(
            conn,
            week_id=week_id,
            scope="weekly",
            narrative_md="Weekly synthesis across four minis.",
            rollup_status="ok",
            prompt_version=WEEKLY_PROMPT_VERSION,
            model_id="gemini-2.5-flash",
            input_token_count=200,
            output_token_count=150,
            cost_usd_estimate=0.0002,
        )
        conn.commit()
        rows = get_rollups_for_week(conn, week_id)
    assert len(rows) == 4
    scopes = {row["scope"] for row in rows}
    assert scopes == {
        "category:edtech",
        "category:business",
        "category:technical",
        "weekly",
    }


def test_rollup_orchestrator_writes_five_rows(apply_schema, monkeypatch) -> None:
    """Integration: _rollup_week inserts five rows when four categories have clusters."""
    from pipeline.orchestrator import RunStats, _rollup_week
    from store.db import insert_story_cluster

    week_id = "2026-W21"
    call_count = {"n": 0}

    def _fake_category(**kwargs) -> RollupResult:
        call_count["n"] += 1
        category = kwargs["category"]
        return RollupResult(
            narrative_md=f"Mini {category}.",
            rollup_status="ok",
            prompt_version=CATEGORY_PROMPT_VERSION,
            model_id="gemini-2.5-flash",
            input_tokens=50,
            output_tokens=40,
            cost_usd_estimate=0.0001,
        )

    def _fake_weekly(**kwargs) -> RollupResult:
        call_count["n"] += 1
        return RollupResult(
            narrative_md="Weekly note.",
            rollup_status="ok",
            prompt_version=WEEKLY_PROMPT_VERSION,
            model_id="gemini-2.5-flash",
            input_tokens=80,
            output_tokens=60,
            cost_usd_estimate=0.0002,
        )

    monkeypatch.setattr("pipeline.llm.rollup.rollup_category", _fake_category)
    monkeypatch.setattr("pipeline.llm.rollup.rollup_weekly", _fake_weekly)

    categories = ("edtech", "business", "technical")
    with connect(apply_schema) as conn:
        conn.execute(
            """
            INSERT INTO sources (source_id, type, url, display_name, tag)
            VALUES ('src-1', 'rss', 'https://example.com/feed', 'Test', 'technical')
            """
        )
        for index, category in enumerate(categories, start=1):
            item_id = f"item-{index}"
            cluster_id = f"cluster-{index}"
            conn.execute(
                """
                INSERT INTO items (
                    item_id, source_id, external_id, canonical_url, title,
                    publisher, published_at, raw_content, content_hash
                ) VALUES (?, 'src-1', ?, ?, ?, 'Test', ?, 'body text', ?)
                """,
                (
                    item_id,
                    f"ext-{index}",
                    f"https://example.com/{index}",
                    f"Story {index}",
                    datetime(2026, 5, 20 + index, tzinfo=UTC).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    f"hash-{index}",
                ),
            )
            insert_story_cluster(
                conn,
                cluster_id=cluster_id,
                week_id=week_id,
                canonical_item_id=item_id,
                canonical_url=f"https://example.com/{index}",
                title_normalized=f"story {index}",
            )
            conn.execute(
                """
                INSERT INTO cluster_members (cluster_id, item_id, is_canonical)
                VALUES (?, ?, 1)
                """,
                (cluster_id, item_id),
            )
            conn.execute(
                """
                INSERT INTO item_summaries (
                    summary_id, item_id, week_id, tldr, summary_confidence,
                    summary_status, prompt_version, model_id
                ) VALUES (?, ?, ?, ?, 'high', 'ok', 'summarize_v1', 'gemini-2.5-flash-lite')
                """,
                (f"sum-{index}", item_id, week_id, f"Summary {index}."),
            )
            conn.execute(
                """
                INSERT INTO cluster_summaries (
                    cluster_summary_id, cluster_id, week_id, category,
                    category_confidence, category_status, prompt_version, model_id
                ) VALUES (?, ?, ?, ?, 'model', 'ok', 'categorize_v1', 'gemini-2.5-flash-lite')
                """,
                (f"cs-{index}", cluster_id, week_id, category),
            )
            conn.execute(
                """
                INSERT INTO cluster_ranks (
                    cluster_rank_id, cluster_id, week_id, rank_score, rank_position,
                    rank_status, prompt_version, model_id
                ) VALUES (?, ?, ?, ?, ?, 'ok', 'rank_v1', 'gemini-2.5-flash')
                """,
                (f"cr-{index}", cluster_id, week_id, float(10 - index), index),
            )
        conn.commit()

        stats = RunStats(week_id=week_id)
        _rollup_week(week_id=week_id, conn=conn, log=MagicMock(), stats=stats)
        rows = get_rollups_for_week(conn, week_id)

    assert len(rows) == 4
    assert call_count["n"] == 4
    assert stats.rollup_llm_calls == 4


def test_rollup_skips_llm_when_rows_exist(apply_schema, monkeypatch) -> None:
    """Stage-level checkpoint skip when rollup rows exist (PIPELINE-05)."""
    from pipeline.orchestrator import RunStats, _rollup_week

    week_id = "2026-W21"
    called = {"rollup": False}

    def _fake_category(**kwargs):
        called["rollup"] = True
        return RollupResult(
            narrative_md="should not run",
            rollup_status="ok",
            prompt_version=CATEGORY_PROMPT_VERSION,
            model_id="gemini-2.5-flash",
        )

    monkeypatch.setattr("pipeline.llm.rollup.rollup_category", _fake_category)

    with connect(apply_schema) as conn:
        for category in CATEGORY_ORDER:
            insert_weekly_rollup(
                conn,
                week_id=week_id,
                scope=scope_for_category(category),  # type: ignore[arg-type]
                narrative_md=f"Cached {category}.",
                rollup_status="ok",
                prompt_version=CATEGORY_PROMPT_VERSION,
                model_id="gemini-2.5-flash",
            )
        insert_weekly_rollup(
            conn,
            week_id=week_id,
            scope="weekly",
            narrative_md="Cached weekly.",
            rollup_status="ok",
            prompt_version=WEEKLY_PROMPT_VERSION,
            model_id="gemini-2.5-flash",
        )
        conn.commit()
        stats = RunStats(week_id=week_id)
        _rollup_week(week_id=week_id, conn=conn, log=MagicMock(), stats=stats)

    assert called["rollup"] is False
    assert stats.rollup_llm_calls == 0
