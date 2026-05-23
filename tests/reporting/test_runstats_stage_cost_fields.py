"""RunStats per-stage cost accumulation (D-09, plan 03-10)."""
from __future__ import annotations

import structlog

from pipeline.llm.categorize import CategorizeResult, PROMPT_VERSION as CATEGORIZE_VERSION
from pipeline.llm.rank import ClusterRankResult, PROMPT_VERSION as RANK_VERSION
from pipeline.llm.summarize import SummaryResult
from pipeline.orchestrator import (
    RunStats,
    _categorize_week_clusters,
    _rank_week,
    _summarize_week_items,
)
from pipeline.week import week_bounds
from store.db import connect, insert_story_cluster


def test_runstats_defines_per_stage_cost_fields() -> None:
    stats = RunStats(week_id="2026-W21")
    assert stats.summarize_cost_usd == 0.0
    assert stats.categorize_cost_usd == 0.0
    assert stats.rank_cost_usd == 0.0
    assert stats.rollup_cost_usd == 0.0


def test_stage_functions_accumulate_per_stage_costs(apply_schema, monkeypatch) -> None:
    """Each LLM stage increments its own cost field; total equals sum of stages."""
    week_id = "2026-W21"
    week_start, week_end = week_bounds(week_id)
    log = structlog.get_logger("test")

    summarize_cost = 0.00003
    categorize_cost = 0.00005
    rank_cost = 0.00007

    def _fake_summarize(**kwargs) -> SummaryResult:
        return SummaryResult(
            tldr="Summary.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            input_tokens=10,
            output_tokens=5,
            cost_usd_estimate=summarize_cost,
        )

    def _fake_categorize(**kwargs) -> CategorizeResult:
        return CategorizeResult(
            category="technical",
            category_confidence="high",
            category_status="ok",
            prompt_version=CATEGORIZE_VERSION,
            model_id="gemini-2.5-flash-lite",
            input_tokens=10,
            output_tokens=5,
            cost_usd_estimate=categorize_cost,
        )

    def _fake_rank(**kwargs) -> list[ClusterRankResult]:
        return [
            ClusterRankResult(
                cluster_id="cluster-1",
                rank_score=50.0,
                rank_position=1,
                rank_status="ok",
                prompt_version=RANK_VERSION,
                model_id="gemini-2.5-flash",
                input_tokens=10,
                output_tokens=5,
                cost_usd_estimate=rank_cost,
            )
        ]

    monkeypatch.setattr("pipeline.llm.summarize.summarize_item", _fake_summarize)
    monkeypatch.setattr("pipeline.llm.categorize.categorize_cluster", _fake_categorize)
    monkeypatch.setattr("pipeline.llm.rank.rank_week_clusters", _fake_rank)

    with connect(apply_schema) as conn:
        conn.execute(
            """
            INSERT INTO sources (source_id, type, url, display_name, tag)
            VALUES ('src-1', 'rss', 'https://example.com/feed', 'Test', 'technical')
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
        conn.commit()

        stats = RunStats(week_id=week_id)
        _summarize_week_items(
            week_id=week_id,
            week_start=week_start,
            week_end=week_end,
            conn=conn,
            log=log,
            stats=stats,
        )
        assert stats.summarize_cost_usd == summarize_cost
        assert stats.categorize_cost_usd == 0.0

        _categorize_week_clusters(week_id=week_id, conn=conn, log=log, stats=stats)
        assert stats.categorize_cost_usd == categorize_cost

        _rank_week(week_id=week_id, conn=conn, log=log, stats=stats)
        assert stats.rank_cost_usd == rank_cost

        expected_total = summarize_cost + categorize_cost + rank_cost
        assert stats.cost_usd_estimate == expected_total
