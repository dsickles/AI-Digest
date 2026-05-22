"""pipeline_report.json schema contract (OBS-02, D-70)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pipeline.config import RssSource, SourceConfig
from pipeline.llm.summarize import SummaryResult
from pipeline.models import NormalizedItem
from pipeline.orchestrator import run_all
from store.db import connect, upsert_source


def _source() -> RssSource:
    return RssSource(
        id="test-source",
        type="rss",
        url="https://example.com/feed",
        display_name="Example Source",
        tag="technical",
        enabled=True,
    )


def test_pipeline_report_schema_keys(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path, tmp_path: Path
) -> None:
    db_path = apply_schema
    out_dir = tmp_path / "out"
    week_id = "2026-W21"
    published = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    item = NormalizedItem.build(
        source_id="test-source",
        external_id="ext-1",
        canonical_url="https://example.com/post-1",
        title="Test Post",
        publisher="Example Source",
        published_at=published,
        raw_content_html="<p>" + " ".join(["word"] * 40) + "</p>",
    )

    class FakeAdapter:
        last_http_status = 200

        def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
            return [item]

    def _fake_summarize(**kwargs) -> SummaryResult:
        return SummaryResult(
            tldr="Grounded summary.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            cost_usd_estimate=0.00003,
        )

    from pipeline.llm.categorize import CategorizeResult
    from pipeline.llm.rollup import RollupResult

    monkeypatch.setattr("pipeline.config.enabled_sources", lambda: [_source()])
    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", lambda _t: FakeAdapter())
    monkeypatch.setattr("pipeline.llm.summarize.summarize_item", _fake_summarize)
    monkeypatch.setattr(
        "pipeline.llm.categorize.categorize_cluster",
        lambda **kw: CategorizeResult(
            category="technical",
            category_confidence="high",
            category_status="ok",
            prompt_version="categorize_v1",
            model_id="gemini-2.5-flash-lite",
        ),
    )
    monkeypatch.setattr("pipeline.llm.rank.rank_week_clusters", lambda **kw: [])
    monkeypatch.setattr(
        "pipeline.llm.rollup.rollup_category",
        lambda **kw: RollupResult(
            narrative_md="Mini",
            rollup_status="ok",
            prompt_version="rollup_category_v1",
            model_id="gemini-2.5-flash",
        ),
    )
    monkeypatch.setattr(
        "pipeline.llm.rollup.rollup_weekly",
        lambda **kw: RollupResult(
            narrative_md="Weekly",
            rollup_status="ok",
            prompt_version="rollup_weekly_v1",
            model_id="gemini-2.5-flash",
        ),
    )

    with connect(db_path) as conn:
        upsert_source(conn, _source())
        conn.commit()

    run_all(week_id, db_path=db_path, out_dir=out_dir)
    per_week = out_dir / f"pipeline-report-{week_id}.json"
    latest = out_dir / "pipeline_report.json"
    assert per_week.exists()
    assert latest.exists()

    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["budget"]["cap_usd"] == 2.0
    assert "dedup" in payload["stages"]
    assert "summary_status" in payload
    assert "source_health" in payload
    assert "test-source" in payload["source_health"]
