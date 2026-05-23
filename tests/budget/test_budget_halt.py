"""Budget halt and partial-publish behavior (D-59, D-60)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.budget import WeekBudget
from pipeline.config import RssSource, SourceConfig
from pipeline.llm.categorize import CategorizeResult
from pipeline.llm.summarize import SummaryResult
from pipeline.models import NormalizedItem
from pipeline.orchestrator import run_all
from pipeline.render.partition import PARTIAL_PUBLISH_COPY
from store.db import connect, fetchone, upsert_item, upsert_source


def _source(source_id: str) -> RssSource:
    return RssSource(
        id=source_id,
        type="rss",
        url="https://example.com/feed",
        display_name="Example Source",
        tag="technical",
        enabled=True,
    )


def _item(*, external_id: str, title: str) -> NormalizedItem:
    published = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)
    return NormalizedItem.build(
        source_id="test-source",
        external_id=external_id,
        canonical_url=f"https://example.com/{external_id}",
        title=title,
        publisher="Example Source",
        published_at=published,
        raw_content_html="<p>" + " ".join(["word"] * 40) + "</p>",
    )


def test_week_budget_can_afford_respects_meta_pool() -> None:
    budget = WeekBudget(cap_usd=0.01, reserved_meta_usd=0.005)
    assert budget.can_afford(0.004, stage="summarize")
    budget.record_spend(0.004, stage="summarize")
    assert not budget.can_afford(0.002, stage="summarize")
    assert budget.can_afford(0.004, stage="categorize")


def test_budget_halt_partial_publish_and_meta_stages(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path, tmp_path: Path
) -> None:
    """Cap 0.01 stops summarize early; categorize still runs; HTML shows notice."""
    db_path = apply_schema
    out_dir = tmp_path / "out"
    week_id = "2026-W21"
    items = [_item(external_id=f"ext-{i}", title=f"Post {i}") for i in range(5)]

    class FakeAdapter:
        last_http_status = 200

        def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
            return items

    call_count = {"n": 0}

    def _fake_summarize(**kwargs) -> SummaryResult:
        call_count["n"] += 1
        return SummaryResult(
            tldr=f"Summary for {kwargs.get('item_id', 'item')}.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            input_tokens=100,
            output_tokens=40,
            cost_usd_estimate=0.008,
        )

    def _fake_categorize(**kwargs) -> CategorizeResult:
        return CategorizeResult(
            category="technical",
            category_confidence="high",
            category_status="ok",
            prompt_version="categorize_v1",
            model_id="gemini-2.5-flash-lite",
            input_tokens=50,
            output_tokens=10,
            cost_usd_estimate=0.0005,
        )

    monkeypatch.setattr("pipeline.config.enabled_sources", lambda: [_source("test-source")])
    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", lambda _t: FakeAdapter())
    monkeypatch.setattr("pipeline.llm.summarize.summarize_item", _fake_summarize)
    monkeypatch.setattr("pipeline.llm.categorize.categorize_cluster", _fake_categorize)
    monkeypatch.setattr(
        "pipeline.llm.rank.rank_week_clusters",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "pipeline.llm.rollup.rollup_category",
        MagicMock(return_value=MagicMock(
            rollup_status="ok",
            narrative_md="Mini.",
            prompt_version="rollup_category_v1",
            model_id="gemini-2.5-flash",
            input_tokens=10,
            output_tokens=10,
            cost_usd_estimate=0.0,
        )),
    )
    monkeypatch.setattr(
        "pipeline.llm.rollup.rollup_weekly",
        MagicMock(return_value=MagicMock(
            rollup_status="ok",
            narrative_md="Weekly.",
            prompt_version="rollup_weekly_v1",
            model_id="gemini-2.5-flash",
            input_tokens=10,
            output_tokens=10,
            cost_usd_estimate=0.0,
        )),
    )

    with connect(db_path) as conn:
        upsert_source(conn, _source("test-source"))
        conn.commit()

    stats = run_all(
        week_id,
        db_path=db_path,
        out_dir=out_dir,
        max_cost_usd=0.015,
    )

    assert call_count["n"] == 1
    assert stats.out_path is not None
    html = stats.out_path.read_text(encoding="utf-8")
    assert "partial-publish-notice" in html
    assert "weekly cost cap" in html
    assert PARTIAL_PUBLISH_COPY in html

    report_path = out_dir / "pipeline_report.json"
    assert report_path.exists()
    import json

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["budget"]["halted"] is True
    assert report["budget"]["halted_at_stage"] == "summarize"

    with connect(db_path) as conn:
        categorized = fetchone(
            conn,
            "SELECT COUNT(*) AS n FROM cluster_summaries WHERE week_id = ?",
            (week_id,),
        )
    assert categorized is not None
    assert int(categorized["n"]) >= 1
