"""WR-02 regression — baseline_per_item_from_runs uses prior ISO week."""
from __future__ import annotations

from pathlib import Path

from pipeline.budget import DEFAULT_BASELINE_PER_ITEM_USD, baseline_per_item_from_runs
from pipeline.week import prior_week_id
from store.db import connect, finalize_pipeline_run, insert_pipeline_run


def _insert_completed_run(
    conn,
    *,
    week_id: str,
    cost_usd_estimate: float,
    summaries_written: int,
    status: str = "success",
) -> None:
    run_id = insert_pipeline_run(conn, week_id=week_id, phase="all", status="running")
    finalize_pipeline_run(
        conn,
        run_id,
        status=status,
        cost_usd_estimate=cost_usd_estimate,
        summaries_written=summaries_written,
    )


def test_prior_week_id_year_boundary() -> None:
    assert prior_week_id("2026-W02") == "2026-W01"
    assert prior_week_id("2026-W01") == "2025-W52"


def test_baseline_uses_prior_week_not_current(apply_schema: Path) -> None:
    """Prior week ratio (0.50/50 = 0.01) wins over current-week row."""
    current_week = "2026-W21"
    prior_week = prior_week_id(current_week)

    with connect(apply_schema) as conn:
        _insert_completed_run(
            conn,
            week_id=prior_week,
            cost_usd_estimate=0.50,
            summaries_written=50,
        )
        _insert_completed_run(
            conn,
            week_id=current_week,
            cost_usd_estimate=1.00,
            summaries_written=10,
            status="partial",
        )
        conn.commit()
        baseline = baseline_per_item_from_runs(conn, current_week)

    assert baseline == 0.01


def test_baseline_fallback_when_no_prior_week(apply_schema: Path) -> None:
    week_id = "2026-W21"
    with connect(apply_schema) as conn:
        baseline = baseline_per_item_from_runs(conn, week_id)

    assert baseline == DEFAULT_BASELINE_PER_ITEM_USD
