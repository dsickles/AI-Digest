"""Pipeline order tests — dedup before summarize (DEDUP-04)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pipeline.config import RssSource, SourceConfig
from pipeline.llm.summarize import SummaryResult
from pipeline.models import NormalizedItem
from pipeline.orchestrator import run_all
from store.db import connect, fetchone, get_existing_summary, upsert_source


def _source(source_id: str, display_name: str) -> RssSource:
    return RssSource(
        id=source_id,
        type="rss",
        url=f"https://example.com/{source_id}/feed",
        display_name=display_name,
        tag="technical",
        enabled=True,
    )


def test_run_all_invokes_dedup_before_summarize(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path, tmp_path: Path
) -> None:
    call_order: list[str] = []
    week_id = "2026-W21"
    published = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)

    items = [
        NormalizedItem.build(
            source_id="src-a",
            external_id="dup-1",
            canonical_url="https://example.com/shared-story?utm=1",
            title="Shared story headline",
            publisher="Source A",
            published_at=published,
            raw_content_html="<p>" + " ".join(["word"] * 40) + "</p>",
        ),
        NormalizedItem.build(
            source_id="src-b",
            external_id="dup-2",
            canonical_url="https://example.com/shared-story",
            title="Shared story headline alt",
            publisher="Source B",
            published_at=published,
            raw_content_html="<p>" + " ".join(["word"] * 20) + "</p>",
        ),
    ]

    class FakeAdapter:
        last_http_status = 200

        def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
            if source.id == "src-a":
                return [items[0]]
            return [items[1]]

    def _fake_enabled_sources() -> list[SourceConfig]:
        return [_source("src-a", "Source A"), _source("src-b", "Source B")]

    import pipeline.orchestrator as orchestrator_module

    real_dedup = orchestrator_module._dedup_week
    real_summarize = orchestrator_module._summarize_week_items

    def _fake_dedup_week(**kwargs) -> int:
        call_order.append("dedup")
        return real_dedup(**kwargs)

    def _fake_summarize_week_items(**kwargs) -> dict[str, SummaryResult]:
        call_order.append("summarize")
        return real_summarize(**kwargs)

    def _fake_summarize_item(**kwargs) -> SummaryResult:
        return SummaryResult(
            tldr="Grounded summary.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            summary_status="ok",
        )

    monkeypatch.setattr("pipeline.config.enabled_sources", _fake_enabled_sources)
    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", lambda _t: FakeAdapter())
    monkeypatch.setattr("pipeline.orchestrator._dedup_week", _fake_dedup_week)
    monkeypatch.setattr(
        "pipeline.orchestrator._summarize_week_items", _fake_summarize_week_items
    )
    monkeypatch.setattr("pipeline.llm.summarize.summarize_item", _fake_summarize_item)

    run_all(week_id, db_path=apply_schema, out_dir=tmp_path / "out")

    assert call_order.index("dedup") < call_order.index("summarize")


def test_non_canonical_member_skips_summary_row(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path, tmp_path: Path
) -> None:
    week_id = "2026-W21"
    published = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)
    db_path = apply_schema

    with connect(db_path) as conn:
        upsert_source(conn, _source("src-a", "Source A"))
        upsert_source(conn, _source("src-b", "Source B"))
        conn.commit()

    items = [
        NormalizedItem.build(
            source_id="src-a",
            external_id="dup-1",
            canonical_url="https://example.com/shared",
            title="Same story",
            publisher="Source A",
            published_at=published,
            raw_content_html="<p>" + " ".join(["alpha"] * 40) + "</p>",
        ),
        NormalizedItem.build(
            source_id="src-b",
            external_id="dup-2",
            canonical_url="https://example.com/shared",
            title="Same story alt",
            publisher="Source B",
            published_at=published,
            raw_content_html="<p>" + " ".join(["beta"] * 10) + "</p>",
        ),
    ]

    class FakeAdapter:
        last_http_status = 200

        def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
            return [items[0]] if source.id == "src-a" else [items[1]]

    summarize_calls: list[str] = []

    def _fake_summarize_item(**kwargs) -> SummaryResult:
        summarize_calls.append(kwargs["item_id"])
        return SummaryResult(
            tldr="Grounded summary.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            summary_status="ok",
        )

    monkeypatch.setattr(
        "pipeline.config.enabled_sources",
        lambda: [_source("src-a", "Source A"), _source("src-b", "Source B")],
    )
    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", lambda _t: FakeAdapter())
    monkeypatch.setattr("pipeline.llm.summarize.summarize_item", _fake_summarize_item)

    run_all(week_id, db_path=db_path, out_dir=tmp_path / "out")

    assert len(summarize_calls) == 1

    with connect(db_path) as conn:
        non_canonical_id = fetchone(
            conn,
            "SELECT item_id FROM items WHERE external_id = 'dup-2'",
        )["item_id"]
        assert non_canonical_id not in summarize_calls
        assert get_existing_summary(conn, non_canonical_id, week_id, "summarize_v1") is None
