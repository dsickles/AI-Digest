"""Same-week run_all idempotency — CR-01 / IN-01 regression."""
from __future__ import annotations

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


def test_run_all_twice_same_week_no_integrity_error(
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
    from pipeline.llm.rank import ClusterRankResult
    from pipeline.llm.rollup import RollupResult

    def _fake_rank(**kw) -> list[ClusterRankResult]:
        clusters = kw.get("clusters", [])
        return [
            ClusterRankResult(
                cluster_id=c.cluster_id,
                rank_score=90.0 - i,
                rank_position=i + 1,
                rank_status="ok",
                prompt_version="rank_v1",
                model_id="gemini-2.5-flash-lite",
            )
            for i, c in enumerate(clusters)
        ]

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
    monkeypatch.setattr("pipeline.llm.rank.rank_week_clusters", _fake_rank)
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
    run_all(week_id, db_path=db_path, out_dir=out_dir)

    digest_path = out_dir / f"digest-{week_id}.html"
    assert digest_path.exists()
    body = digest_path.read_text(encoding="utf-8")
    assert "Briefing — Top" in body

    assert (out_dir / "pipeline_report.json").exists()
