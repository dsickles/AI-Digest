"""Wave 0 RED stub — $1/week LLM hard cap with deferred_budget marking (REQ-OPS-05, D-B9).

Expected to FAIL until Plan 05-03 implements:
- ``pipeline.budget.WeekBudget`` configured at $1.00 hard cap from
  ``config/digest.yaml`` ``pipeline.hard_stop_usd``
- Halt-and-mark behavior writing ``summary_status='deferred_budget'``
  (NOT just ``break``) to ``item_summaries``
- ``pipeline.reporting.pipeline_report`` emitting ``budget.hard_cap_hit``
  and ``budget.deferred_items_count``
- Cross-run weekly spend loaded from ``pipeline_runs`` SUM so the
  Sunday cron and the daily-retry workflow share one counter (D-B4 + D-B9)

LOCKED-01: ``deferred_budget`` routes to the main feed as an
in-place-degraded card, NOT the footer aside. Footer aside is
``summary_status='thin'`` only.
"""
from __future__ import annotations

import pytest


def test_deferred_budget_is_a_valid_summary_status() -> None:
    """Plan 05-03 must register ``deferred_budget`` as a recognized
    ``summary_status`` value used by the orchestrator halt-and-mark path."""
    from pipeline.render.partition import _IN_PLACE_TRANSIENT_STATUSES

    assert "deferred_budget" in _IN_PLACE_TRANSIENT_STATUSES, (
        "Plan 05-03 must add 'deferred_budget' to "
        "pipeline.render.partition._IN_PLACE_TRANSIENT_STATUSES "
        "(LOCKED-01 in-place routing per D-B9)"
    )


def test_pipeline_report_emits_hard_cap_hit_field() -> None:
    """Plan 05-03 must add ``budget.hard_cap_hit`` to pipeline_report.json."""
    from pipeline.reporting import pipeline_report

    source = (pipeline_report.__file__ or "").lower()
    pytest.importorskip("pipeline.reporting.pipeline_report")
    with open(pipeline_report.__file__, encoding="utf-8") as fh:
        text = fh.read()
    assert "hard_cap_hit" in text, (
        "Plan 05-03 must emit budget.hard_cap_hit "
        "(consumed by StatusBanner per OBS-03)"
    )
    assert "deferred_items_count" in text, (
        "Plan 05-03 must emit budget.deferred_items_count for the reader banner"
    )


def test_weekbudget_hard_cap_halts_and_marks_items() -> None:
    """Plan 05-03 must extend WeekBudget so reaching the cap halts new LLM
    calls AND writes ``summary_status='deferred_budget'`` to unprocessed items.

    Today's WeekBudget halts but does not mark — this test pins the new
    contract from D-B9.
    """
    pytest.importorskip("pipeline.budget")
    from pipeline.budget import WeekBudget

    has_mark_hook = hasattr(WeekBudget, "mark_deferred_budget") or hasattr(
        WeekBudget, "deferred_items"
    )
    assert has_mark_hook, (
        "Plan 05-03 must add a deferred-budget marking hook to "
        "pipeline.budget.WeekBudget (D-B9 halt-and-mark)"
    )


def test_cross_run_weekly_spend_loaded_from_pipeline_runs_sum() -> None:
    """Plan 05-03 must load the weekly spend counter from
    ``pipeline_runs`` SUM so Sunday cron + daily retry share one bucket."""
    pytest.importorskip("pipeline.budget")
    from pipeline.budget import WeekBudget

    method = getattr(WeekBudget, "weekly_spend_from_runs", None) or getattr(
        WeekBudget, "load_weekly_spend", None
    )
    assert method is not None, (
        "Plan 05-03 must add a weekly-spend loader that SUMs pipeline_runs "
        "for the active week (D-B4 + D-B9 shared counter)"
    )
