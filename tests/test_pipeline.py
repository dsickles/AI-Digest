"""CLI integration tests — --week threading and render/LLM isolation."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.config import SourceConfig
from pipeline.llm.summarize import SummaryResult
from pipeline.models import NormalizedItem
from pipeline.orchestrator import RunStats, run_all
from store.db import connect, fetchone, init_db


def _source(source_id: str) -> SourceConfig:
    return SourceConfig(
        id=source_id,
        type="rss",
        url="https://example.com/feed",
        display_name="Example Source",
        tag="technical",
        enabled=True,
    )


def test_run_all_finalizes_pipeline_run(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path, tmp_path: Path
) -> None:
    """run_all writes a pipeline_runs row with finished_at and numeric metrics."""
    db_path = apply_schema
    out_dir = tmp_path / "out"
    week_id = "2026-W21"
    published = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)

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

    def _fake_enabled_sources() -> list[SourceConfig]:
        return [_source("test-source")]

    def _fake_summarize_item(**kwargs) -> SummaryResult:
        return SummaryResult(
            tldr="A grounded two-sentence summary for testing.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            input_tokens=120,
            output_tokens=45,
            cost_usd_estimate=0.00003,
        )

    monkeypatch.setattr("pipeline.config.enabled_sources", _fake_enabled_sources)
    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", lambda _t: FakeAdapter())
    monkeypatch.setattr("pipeline.llm.summarize.summarize_item", _fake_summarize_item)

    stats = run_all(week_id, db_path=db_path, out_dir=out_dir)
    assert stats.items_fetched == 1
    assert stats.summaries_written == 1
    assert stats.out_path is not None
    assert stats.out_path.exists()

    with connect(db_path) as conn:
        row = fetchone(
            conn,
            """
            SELECT finished_at, status, items_fetched, summaries_written,
                   items_degraded, cost_usd_estimate, errors_json
              FROM pipeline_runs
             WHERE week_id = ? AND phase = 'all'
             ORDER BY started_at DESC
             LIMIT 1
            """,
            (week_id,),
        )
    assert row is not None
    assert row["finished_at"] is not None
    assert row["items_fetched"] == 1
    assert row["summaries_written"] == 1
    assert row["items_degraded"] == 0
    assert row["cost_usd_estimate"] > 0
    assert row["status"] in ("success", "partial")
    assert '"phase"' not in row["errors_json"] or row["errors_json"].startswith("[")


def test_ingest_logs_include_source_id(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path
) -> None:
    """ingest_fetch events include source_id for observability (D-07)."""
    from structlog.testing import capture_logs

    item = NormalizedItem.build(
        source_id="log-source",
        external_id="ext-log",
        canonical_url="https://example.com/log",
        title="Log Test",
        publisher="Log Source",
        published_at=datetime(2026, 5, 20, tzinfo=UTC),
        raw_content_html="<p>body</p>",
    )

    class FakeAdapter:
        last_http_status = 200

        def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
            return [item]

    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", lambda _t: FakeAdapter())

    from pipeline.orchestrator import RunStats, _ingest
    from store.db import upsert_source
    import structlog

    log = structlog.get_logger("test").bind(week_id="2026-W21")
    stats = RunStats(week_id="2026-W21", phase="ingest")
    with capture_logs() as cap:
        with connect(apply_schema) as conn:
            upsert_source(conn, _source("log-source"))
            conn.commit()
            _ingest([_source("log-source")], conn, log, stats)

    start_events = [e for e in cap if e.get("event") == "ingest_fetch_start"]
    assert start_events, f"expected ingest_fetch_start in {cap!r}"
    assert start_events[0].get("source_id") == "log-source"


def test_week_override_threads_to_orchestrator(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path
) -> None:
    """--week 2026-W19 flows through the CLI to orchestrator.run_all."""
    captured: dict[str, str] = {}

    def _fake_run_all(week_id: str, **kwargs) -> RunStats:
        captured["week_id"] = week_id
        return RunStats(week_id=week_id, out_path=Path("out/digest-2026-W19.html"))

    monkeypatch.setattr("pipeline.orchestrator.run_all", _fake_run_all)

    from pipeline.run import main

    rc = main(["all", "--week", "2026-W19"])
    assert rc == 0
    assert captured["week_id"] == "2026-W19"


def test_bare_cli_aliases_all_with_week(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path
) -> None:
    """Bare python -m pipeline.run --week aliases all (D-19)."""
    captured: dict[str, str] = {}

    def _fake_run_all(week_id: str, **kwargs) -> RunStats:
        captured["week_id"] = week_id
        return RunStats(week_id=week_id)

    monkeypatch.setattr("pipeline.orchestrator.run_all", _fake_run_all)

    from pipeline.run import main

    rc = main(["--week", "2026-W19"])
    assert rc == 0
    assert captured["week_id"] == "2026-W19"


def test_render_does_not_call_llm(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path, tmp_path: Path
) -> None:
    """Render subcommand must not invoke summarize / LLM (D-20)."""
    def _summarize_must_not_run(*_args, **_kwargs):
        raise AssertionError("summarize must not run during render")

    monkeypatch.setattr(
        "pipeline.orchestrator._summarize_week_items",
        _summarize_must_not_run,
    )
    monkeypatch.setattr(
        "pipeline.orchestrator.run_render",
        lambda week_id, **kw: RunStats(
            week_id=week_id,
            out_path=tmp_path / f"digest-{week_id}.html",
        ),
    )

    from pipeline.run import main

    rc = main(["render", "--week", "2026-W19"])
    assert rc == 0


def test_render_import_does_not_load_adapters_or_llm() -> None:
    """Importing run_render in a fresh process must not pull adapters or LLM."""
    import subprocess
    import sys

    script = """
import sys
for name in list(sys.modules):
    if name.startswith("pipeline.") or name.startswith("google"):
        del sys.modules[name]
from pipeline.orchestrator import run_render  # noqa: F401
loaded = [
    m for m in sys.modules
    if m.startswith("pipeline.adapters")
    or m.startswith("pipeline.llm")
    or m.startswith("google.genai")
]
if loaded:
    raise SystemExit(f"unexpected imports: {loaded}")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0, result.stderr or result.stdout
