"""Structured JSON run report projection (OBS-02, D-69, D-70).

Builds ``out/pipeline-report-{week_id}.json`` and ``out/pipeline_report.json``
from ``RunStats`` + SQLite aggregates — not a parallel substrate (D-09).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pipeline.budget import WeekBudget
    from pipeline.orchestrator import RunStats

DEFAULT_OUT_DIR = Path("out")
DEFAULT_ARCHIVE_DIR = Path("web/src/content/reports")

_SUMMARY_STATUS_KEYS = (
    "ok",
    "thin",
    "quota_exhausted",
    "api_error",
    "parse_error",
    "client_init_error",
    # Phase 5 D-B9: cap-deferred items show as an in-place degraded
    # card per LOCKED-01 amendment in plan 05-03.
    "deferred_budget",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _summary_status_counts(
    conn: sqlite3.Connection, week_id: str
) -> dict[str, int]:
    counts = {key: 0 for key in _SUMMARY_STATUS_KEYS}
    rows = conn.execute(
        """
        SELECT summary_status, COUNT(*) AS n
          FROM item_summaries
         WHERE week_id = ?
         GROUP BY summary_status
        """,
        (week_id,),
    ).fetchall()
    for row in rows:
        status = row["summary_status"]
        if status in counts:
            counts[status] = int(row["n"])
        elif status is None:
            counts["thin"] += int(row["n"])
    return counts


def _categorize_distribution(
    conn: sqlite3.Connection, week_id: str
) -> dict[str, int]:
    base = {
        "edtech": 0,
        "business": 0,
        "technical": 0,
        "fallback_source_tag": 0,
    }
    rows = conn.execute(
        """
        SELECT category, category_confidence, COUNT(*) AS n
          FROM cluster_summaries
         WHERE week_id = ?
         GROUP BY category, category_confidence
        """,
        (week_id,),
    ).fetchall()
    for row in rows:
        cat = row["category"]
        conf = row["category_confidence"]
        n = int(row["n"])
        if conf == "fallback_source_tag":
            base["fallback_source_tag"] += n
        elif cat in base:
            base[cat] += n
    return base


def _source_health_snapshot(
    conn: sqlite3.Connection, week_id: str
) -> dict[str, dict[str, Any]]:
    week_start, week_end = _week_bounds_iso(week_id)
    sources = conn.execute(
        """
        SELECT source_id, last_success_at, last_error_category
          FROM sources
        """
    ).fetchall()
    health: dict[str, dict[str, Any]] = {}
    for src in sources:
        sid = src["source_id"]
        items_row = conn.execute(
            """
            SELECT COUNT(*) AS n
              FROM items
             WHERE source_id = ?
               AND published_at >= ?
               AND published_at <= ?
            """,
            (sid, week_start, week_end),
        ).fetchone()
        canon_row = conn.execute(
            """
            SELECT COUNT(DISTINCT sc.cluster_id) AS n
              FROM story_clusters sc
              JOIN items i ON i.item_id = sc.canonical_item_id
             WHERE sc.week_id = ?
               AND i.source_id = ?
            """,
            (week_id, sid),
        ).fetchone()
        err = src["last_error_category"]
        health[sid] = {
            "last_success_at": src["last_success_at"],
            "last_error_category": err if err else None,
            "items_this_week": int(items_row["n"]) if items_row else 0,
            "clusters_canonical_this_week": int(canon_row["n"]) if canon_row else 0,
        }
    return health


def _week_bounds_iso(week_id: str) -> tuple[str, str]:
    from pipeline.week import week_bounds

    start, end = week_bounds(week_id)
    return (
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _rollup_stage_metrics(
    conn: sqlite3.Connection, week_id: str, stats: RunStats
) -> dict[str, Any]:
    mini_count = conn.execute(
        """
        SELECT COUNT(*) AS n
          FROM weekly_rollups
         WHERE week_id = ?
           AND scope LIKE 'category:%'
        """,
        (week_id,),
    ).fetchone()
    weekly_row = conn.execute(
        """
        SELECT 1 FROM weekly_rollups
         WHERE week_id = ? AND scope = 'weekly'
         LIMIT 1
        """,
        (week_id,),
    ).fetchone()
    return {
        "mini_rollups": int(mini_count["n"]) if mini_count else 0,
        "weekly": weekly_row is not None,
        "llm_calls": stats.rollup_llm_calls,
        "cost_usd": round(stats.rollup_cost_usd, 6),
    }


def build_pipeline_report(
    conn: sqlite3.Connection,
    stats: RunStats,
    *,
    run_id: str,
    status: str,
    budget: WeekBudget | None,
) -> dict[str, Any]:
    """Assemble schema_version 1 payload from run stats and SQL aggregates."""
    week_id = stats.week_id
    cluster_row = conn.execute(
        "SELECT COUNT(*) AS n FROM story_clusters WHERE week_id = ?",
        (week_id,),
    ).fetchone()
    clusters = int(cluster_row["n"]) if cluster_row else 0

    budget_block: dict[str, Any]
    if budget is not None:
        # Phase 5 D-B9: hard_cap_hit is currently identical to `halted`
        # — we keep both fields because StatusBanner (OBS-03) reads
        # hard_cap_hit while pipeline notes / dev tools still read
        # halted; should the semantics ever diverge (e.g. a soft cap),
        # the reader-surface field can stay stable without renaming.
        budget_block = {
            "cap_usd": budget.cap_usd,
            "reserved_meta_usd": budget.reserved_meta_usd,
            "spent_usd": round(budget.spent_usd, 6),
            "pre_flight_estimate_usd": round(budget.pre_flight_estimate_usd, 6),
            "halted": budget.halted,
            "halted_at_stage": budget.halted_at_stage,
            "hard_cap_hit": bool(budget.halted),
            "deferred_items_count": len(budget.deferred_items),
        }
    else:
        cfg = __import__("pipeline.config", fromlist=["load_digest_config"]).load_digest_config()
        budget_block = {
            "cap_usd": cfg.pipeline.hard_stop_usd,
            "reserved_meta_usd": cfg.pipeline.meta_reservation_usd,
            "spent_usd": round(stats.cost_usd_estimate, 6),
            "pre_flight_estimate_usd": 0.0,
            "halted": False,
            "halted_at_stage": None,
            "hard_cap_hit": False,
            "deferred_items_count": 0,
        }

    return {
        "schema_version": 1,
        "week_id": week_id,
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "status": status,
        "items_ingested": stats.items_fetched,
        "clusters": clusters,
        "llm_calls": stats.llm_calls,
        "cost_usd": round(stats.cost_usd_estimate, 6),
        "errors": stats.errors,
        "summary_status": _summary_status_counts(conn, week_id),
        "stages": {
            "ingest": {"items": stats.items_fetched},
            "dedup": {
                "clusters_created": stats.clusters_created,
                "items_clustered": stats.items_clustered,
            },
            "summarize": {
                "llm_calls": stats.llm_calls
                - stats.categorize_llm_calls
                - stats.rank_llm_calls
                - stats.rollup_llm_calls,
                "cost_usd": round(stats.summarize_cost_usd, 6),
                "summaries_written": stats.summaries_written,
                "items_degraded": stats.items_degraded,
            },
            "categorize": {
                "llm_calls": stats.categorize_llm_calls,
                "cost_usd": round(stats.categorize_cost_usd, 6),
                "distribution": _categorize_distribution(conn, week_id),
            },
            "rank": {
                "llm_calls": stats.rank_llm_calls,
                "cost_usd": round(stats.rank_cost_usd, 6),
            },
            "rollup": _rollup_stage_metrics(conn, week_id, stats),
        },
        "source_health": _source_health_snapshot(conn, week_id),
        "budget": budget_block,
    }


def write_pipeline_report(
    conn: sqlite3.Connection,
    stats: RunStats,
    *,
    run_id: str,
    status: str,
    budget: WeekBudget | None = None,
    out_dir: Path | None = None,
    archive_dir: Path | None = DEFAULT_ARCHIVE_DIR,
) -> tuple[Path, Path]:
    """Write per-week and always-latest JSON artifacts (D-69).

    When ``archive_dir`` is set, also writes ``{week_id}.json`` for the Astro
    content collection at ``web/src/content/reports/`` (D-A2a).
    """
    target_dir = out_dir or DEFAULT_OUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = build_pipeline_report(
        conn, stats, run_id=run_id, status=status, budget=budget
    )
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    per_week = target_dir / f"pipeline-report-{stats.week_id}.json"
    latest = target_dir / "pipeline_report.json"
    per_week.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    if archive_dir is not None:
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{stats.week_id}.json"
        archive_path.write_text(text, encoding="utf-8")
    return per_week, latest


__all__ = ["build_pipeline_report", "write_pipeline_report"]
