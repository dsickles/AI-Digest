"""$1/week LLM hard cap with deferred_budget marking (REQ-OPS-05, D-B9).

Wave 0 of plan 05-01 landed these as RED contract stubs; plan 05-03
turns them GREEN and adds an end-to-end integration test that exercises
``run_all`` with an artificially low cap (mirrors the
``tests/budget/test_budget_halt.py`` pattern).

Three layers of coverage:

1. Surface contracts — ``deferred_budget`` is a valid
   ``_IN_PLACE_TRANSIENT_STATUSES`` member; pipeline report exposes
   ``hard_cap_hit`` + ``deferred_items_count``; ``WeekBudget`` exports
   the deferred-marking and weekly-spend hooks the orchestrator needs.

2. Cross-run weekly spend — ``get_cumulative_week_spend_usd`` sums
   ``pipeline_runs.cost_usd_estimate`` for the active week so the
   Sunday cron and the Mon–Sat daily-retry workflow share one bucket.

3. End-to-end — a sub-cap run halts summarize early, every unprocessed
   canonical item gets ``summary_status='deferred_budget'`` in
   ``item_summaries``, the digest still publishes, and the per-week
   pipeline-report JSON has ``budget.hard_cap_hit=True`` plus
   ``budget.deferred_items_count > 0``.

LOCKED-01 (PROJECT.md, refined 2026-05-23): ``deferred_budget`` routes
to the main feed as an in-place-degraded card, NEVER the footer aside.
Footer aside is ``summary_status='thin'`` only.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.budget import (
    HARD_CAP_USD_ENV,
    WeekBudget,
    get_cumulative_week_spend_usd,
)
from pipeline.config import RssSource, SourceConfig
from pipeline.llm.categorize import CategorizeResult
from pipeline.llm.summarize import SummaryResult
from pipeline.models import NormalizedItem
from pipeline.orchestrator import run_all
from store.db import connect, fetchone, insert_pipeline_run, upsert_source


# ----------------- surface contracts ---------------------------------


def test_deferred_budget_is_a_valid_summary_status() -> None:
    """Plan 05-03 registers ``deferred_budget`` as an in-place status
    so LOCKED-01 routes the card to the main feed, not the footer."""
    from pipeline.render.partition import _IN_PLACE_TRANSIENT_STATUSES

    assert "deferred_budget" in _IN_PLACE_TRANSIENT_STATUSES


def test_pipeline_report_emits_hard_cap_hit_field() -> None:
    """``budget.hard_cap_hit`` and ``budget.deferred_items_count`` are
    the reader-banner inputs (consumed by ``StatusBanner.astro``)."""
    from pipeline.reporting import pipeline_report

    with open(pipeline_report.__file__, encoding="utf-8") as fh:
        text = fh.read()
    assert "hard_cap_hit" in text
    assert "deferred_items_count" in text


def test_weekbudget_hard_cap_halts_and_marks_items() -> None:
    """``WeekBudget`` exports the deferred-marking hook the
    orchestrator's halt path needs."""
    assert callable(getattr(WeekBudget, "mark_deferred_budget", None))
    # ``deferred_items`` is a dataclass field with default_factory=list
    # so it lives on instances, not the class.
    sample = WeekBudget(cap_usd=1.0, reserved_meta_usd=0.10)
    assert sample.deferred_items == []
    sample.mark_deferred_budget("item-xyz")
    assert sample.deferred_items == ["item-xyz"]
    sample.mark_deferred_budget("item-xyz")  # idempotent
    assert sample.deferred_items == ["item-xyz"]


def test_cross_run_weekly_spend_loaded_from_pipeline_runs_sum() -> None:
    """``WeekBudget.load_weekly_spend`` is the shared-counter loader
    used by cron and daily-retry (D-B4 + D-B9)."""
    assert callable(getattr(WeekBudget, "load_weekly_spend", None))


# ----------------- env override + cumulative spend -------------------


def test_hard_cap_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """``HARD_CAP_USD=0.25`` overrides config; ``cap_override`` still wins."""
    monkeypatch.setenv(HARD_CAP_USD_ENV, "0.25")
    budget = WeekBudget.from_config()
    assert budget.cap_usd == pytest.approx(0.25)

    # CLI flag (--max-cost-usd) still has the highest precedence.
    budget_explicit = WeekBudget.from_config(cap_override=0.50)
    assert budget_explicit.cap_usd == pytest.approx(0.50)


def test_hard_cap_env_invalid_falls_back_to_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo'd / non-positive ``HARD_CAP_USD`` must not crash; it
    silently falls back to ``config/digest.yaml``."""
    for bad in ("not-a-number", "", "0", "-1.0", "abc"):
        monkeypatch.setenv(HARD_CAP_USD_ENV, bad)
        budget = WeekBudget.from_config()
        assert budget.cap_usd == pytest.approx(1.0)  # config default


def test_cumulative_week_spend_aggregates_across_runs(
    apply_schema: Path,
) -> None:
    """Two prior runs in the same week sum into the shared counter."""
    week_id = "2026-W30"
    with connect(apply_schema) as conn:
        run_a = insert_pipeline_run(conn, week_id=week_id, phase="all", status="success")
        run_b = insert_pipeline_run(conn, week_id=week_id, phase="summarize", status="partial")
        conn.execute(
            "UPDATE pipeline_runs SET cost_usd_estimate = ? WHERE run_id = ?",
            (0.40, run_a),
        )
        conn.execute(
            "UPDATE pipeline_runs SET cost_usd_estimate = ? WHERE run_id = ?",
            (0.25, run_b),
        )
        conn.commit()

        spend = get_cumulative_week_spend_usd(conn, week_id)
        assert spend == pytest.approx(0.65)
        assert WeekBudget.load_weekly_spend(conn, week_id) == pytest.approx(0.65)

        # Different week stays at zero.
        assert get_cumulative_week_spend_usd(conn, "2026-W31") == 0.0


def test_weekbudget_from_config_seeds_spent_from_prior_runs(
    apply_schema: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``from_config(conn, week_id)`` carries cross-run spend forward."""
    monkeypatch.delenv(HARD_CAP_USD_ENV, raising=False)
    week_id = "2026-W31"
    with connect(apply_schema) as conn:
        run_id = insert_pipeline_run(
            conn, week_id=week_id, phase="all", status="success"
        )
        conn.execute(
            "UPDATE pipeline_runs SET cost_usd_estimate = ? WHERE run_id = ?",
            (0.85, run_id),
        )
        conn.commit()

        budget = WeekBudget.from_config(conn=conn, week_id=week_id)
    assert budget.spent_usd == pytest.approx(0.85)
    # _spent_on_summarize is also seeded so the per-item afford check
    # reflects what's already been spent on summarize work.
    assert budget._spent_on_summarize == pytest.approx(0.85)


# ----------------- end-to-end run_all halt + mark + publish ---------


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


def test_run_all_hard_cap_marks_deferred_and_publishes(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path, tmp_path: Path
) -> None:
    """End-to-end: low cap halts summarize → unprocessed canonical
    items get ``deferred_budget`` rows → digest JSON still emits →
    report JSON shows ``hard_cap_hit=True`` and a positive
    ``deferred_items_count``."""
    monkeypatch.delenv(HARD_CAP_USD_ENV, raising=False)
    db_path = apply_schema
    out_dir = tmp_path / "out"
    week_id = "2026-W21"
    items = [_item(external_id=f"ext-{i}", title=f"Post {i}") for i in range(5)]

    def _fake_summarize(**kwargs) -> SummaryResult:
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

    class FakeAdapter:
        last_http_status = 200

        def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
            return items

    monkeypatch.setattr("pipeline.config.enabled_sources", lambda: [_source("test-source")])
    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", lambda _t: FakeAdapter())
    monkeypatch.setattr("pipeline.llm.summarize.summarize_item", _fake_summarize)
    monkeypatch.setattr("pipeline.llm.categorize.categorize_cluster", _fake_categorize)
    monkeypatch.setattr("pipeline.llm.rank.rank_week_clusters", lambda **kwargs: [])
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
    assert stats.out_path is not None  # digest still publishes despite halt

    # Some items got a real summary, the rest were deferred.
    with connect(db_path) as conn:
        deferred_row = fetchone(
            conn,
            """
            SELECT COUNT(*) AS n
              FROM item_summaries
             WHERE week_id = ?
               AND summary_status = 'deferred_budget'
            """,
            (week_id,),
        )
    assert deferred_row is not None
    deferred_count = int(deferred_row["n"])
    assert deferred_count > 0, "Halt must mark unprocessed items deferred_budget"
    assert deferred_count < len(items), "At least one summary should land before halt"

    report_path = out_dir / "pipeline_report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["budget"]["hard_cap_hit"] is True
    assert report["budget"]["deferred_items_count"] == deferred_count
    assert report["budget"]["halted"] is True
    assert report["summary_status"]["deferred_budget"] == deferred_count
