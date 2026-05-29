"""Daily-retry CLI surface (REQ-OPS-01, D-B4 + D-B9).

``--retry-transient-only`` on ``pipeline.run summarize`` re-processes only
items whose ``summary_status`` is a transient LLM failure
(``quota_exhausted``, ``api_error``, ``client_init_error``). Cap-deferred
items (``deferred_budget``) are explicitly excluded.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from pipeline.config import RssSource
from pipeline.llm.summarize import SummaryResult
from pipeline.models import NormalizedItem
from pipeline.orchestrator import (
    TRANSIENT_RETRY_STATUSES,
    retry_transient_summaries,
    run_summarize,
)
from store.db import connect, insert_item_summary, upsert_item, upsert_source


def test_summarize_retry_transient_only_flag_in_help() -> None:
    """``--retry-transient-only`` appears on summarize --help (D-22)."""
    result = subprocess.run(
        [sys.executable, "-m", "pipeline.run", "summarize", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "--retry-transient-only" in result.stdout


def test_orchestrator_exposes_retry_transient_only_entrypoint() -> None:
    """Orchestrator exports ``retry_transient_summaries`` for the daily-retry path."""
    assert callable(retry_transient_summaries)


def test_retry_scope_excludes_deferred_budget() -> None:
    """``TRANSIENT_RETRY_STATUSES`` excludes ``deferred_budget`` (D-B9)."""
    scope = TRANSIENT_RETRY_STATUSES
    assert "deferred_budget" not in scope
    assert {"quota_exhausted", "api_error", "client_init_error"} <= set(scope)


def _rss_source() -> RssSource:
    return RssSource(
        id="retry-test-source",
        type="rss",
        url="https://example.com/feed",
        display_name="Retry Test",
        tag="technical",
        enabled=True,
    )


def _item(*, external_id: str) -> NormalizedItem:
    published = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)
    return NormalizedItem.build(
        source_id="retry-test-source",
        external_id=external_id,
        canonical_url=f"https://example.com/{external_id}",
        title=f"Post {external_id}",
        publisher="Retry Test",
        published_at=published,
        raw_content_html="<p>" + " ".join(["word"] * 40) + "</p>",
    )


def _seed_summary(
    conn,
    *,
    week_id: str,
    external_id: str,
    summary_status: str,
) -> str:
    item_id = upsert_item(conn, _item(external_id=external_id))
    insert_item_summary(
        conn,
        item_id=item_id,
        week_id=week_id,
        tldr=None,
        summary_confidence="unavailable",
        prompt_version="summarize_v1",
        model_id="",
        summary_status=summary_status,
    )
    return item_id


def test_run_summarize_retry_transient_only_processes_quota_exhausted(
    monkeypatch: pytest.MonkeyPatch,
    apply_schema,
) -> None:
    """Transient ``quota_exhausted`` rows are re-summarized."""
    db_path = apply_schema
    week_id = "2026-W21"
    attempted: list[str] = []

    def _fake_summarize(**kwargs) -> SummaryResult:
        item_id = kwargs["item_id"]
        attempted.append(item_id)
        return SummaryResult(
            tldr=f"Recovered summary for {item_id}.",
            summary_confidence="high",
            prompt_version="summarize_v1",
            model_id="gemini-2.5-flash-lite",
            input_tokens=50,
            output_tokens=20,
            cost_usd_estimate=0.001,
            summary_status="ok",
        )

    monkeypatch.setattr(
        "pipeline.llm.summarize.summarize_item",
        _fake_summarize,
    )

    with connect(db_path) as conn:
        upsert_source(conn, _rss_source())
        quota_id = _seed_summary(
            conn, week_id=week_id, external_id="quota", summary_status="quota_exhausted"
        )
        _seed_summary(
            conn, week_id=week_id, external_id="deferred", summary_status="deferred_budget"
        )
        conn.commit()

    stats = run_summarize(week_id, db_path=db_path, retry_transient_only=True)

    assert attempted == [quota_id]
    assert stats.summaries_written == 1


def test_run_summarize_retry_transient_only_skips_deferred_budget(
    monkeypatch: pytest.MonkeyPatch,
    apply_schema,
) -> None:
    """``deferred_budget`` rows are never passed to ``summarize_item``."""
    db_path = apply_schema
    week_id = "2026-W21"
    mock_summarize = MagicMock()
    monkeypatch.setattr(
        "pipeline.llm.summarize.summarize_item",
        mock_summarize,
    )

    with connect(db_path) as conn:
        upsert_source(conn, _rss_source())
        _seed_summary(
            conn, week_id=week_id, external_id="deferred", summary_status="deferred_budget"
        )
        conn.commit()

    run_summarize(week_id, db_path=db_path, retry_transient_only=True)

    mock_summarize.assert_not_called()
