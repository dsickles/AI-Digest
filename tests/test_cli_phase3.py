"""Phase 3 CLI discoverability and idempotency (D-22, PIPELINE-05/06)."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pipeline.config import RssSource
from pipeline.llm.summarize import SummaryResult
from pipeline.models import NormalizedItem
from pipeline.orchestrator import run_render, run_summarize
from store.db import connect, insert_item_summary, upsert_item, upsert_source


def test_help_lists_phase3_subcommands_and_flags() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pipeline.run", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = proc.stdout
    for token in (
        "dedup",
        "categorize",
        "rank",
        "rollup",
        "--top-n",
        "--max-cost-usd",
        "--rebuild-clusters",
        "--rebuild-rollup",
    ):
        assert token in out


def test_double_render_produces_identical_html(
    apply_schema: Path, tmp_path: Path
) -> None:
    """PIPELINE-05: re-render without upstream changes is byte-identical."""
    db_path = apply_schema
    out_dir = tmp_path / "out"
    week_id = "2026-W21"
    source = RssSource(
        id="cli-source",
        type="rss",
        url="https://example.com/feed",
        display_name="CLI Source",
        tag="technical",
        enabled=True,
    )
    item = NormalizedItem.build(
        source_id=source.id,
        external_id="ext-render",
        canonical_url="https://example.com/render",
        title="Render twice",
        publisher="CLI Source",
        published_at=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
        raw_content_html="<p>" + " ".join(["word"] * 40) + "</p>",
    )
    with connect(db_path) as conn:
        upsert_source(conn, source)
        item_id = upsert_item(conn, item)
        insert_item_summary(
            conn,
            item_id=item_id,
            week_id=week_id,
            tldr="Stable summary for idempotent render test.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            summary_status="ok",
        )
        conn.commit()

    run_render(week_id, db_path=db_path, out_dir=out_dir)
    path = out_dir / f"digest-{week_id}.html"
    first = path.read_bytes()
    run_render(week_id, db_path=db_path, out_dir=out_dir)
    second = path.read_bytes()
    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()


def test_partial_summarize_resume_skips_completed(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path, tmp_path: Path
) -> None:
    """PIPELINE-06: checkpoint skips items that already have summaries."""
    db_path = apply_schema
    week_id = "2026-W21"
    source = RssSource(
        id="chk-source",
        type="rss",
        url="https://example.com/feed",
        display_name="Chk",
        tag="technical",
        enabled=True,
    )
    items = [
        NormalizedItem.build(
            source_id=source.id,
            external_id=f"ext-{i}",
            canonical_url=f"https://example.com/{i}",
            title=f"Item {i}",
            publisher="Chk",
            published_at=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
            raw_content_html="<p>" + " ".join(["word"] * 40) + "</p>",
        )
        for i in range(3)
    ]
    with connect(db_path) as conn:
        upsert_source(conn, source)
        item_ids = []
        for it in items:
            item_ids.append(upsert_item(conn, it))
        insert_item_summary(
            conn,
            item_id=item_ids[0],
            week_id=week_id,
            tldr="Already done.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            summary_status="ok",
        )
        conn.commit()

    called: list[str] = []

    def _fake_summarize(**kwargs) -> SummaryResult:
        called.append(kwargs["item_id"])
        return SummaryResult(
            tldr="New summary.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            cost_usd_estimate=0.001,
        )

    monkeypatch.setattr("pipeline.llm.summarize.summarize_item", _fake_summarize)

    stats = run_summarize(week_id, db_path=db_path, out_dir=tmp_path / "out")
    assert item_ids[0] not in called
    assert stats.summaries_written == 2
