"""End-to-end orchestrator — wires ingest → store → summarize → render.

Public entry points: ``run_ingest``, ``run_summarize``, ``run_render``, ``run_all``.
Each accepts ``week_id: str`` only — callers (CLI) resolve the current week.

Per-source try/except gives us PROJECT.md per-source isolation
(one bad feed cannot break the weekly run) even though the formal
INGEST-06 requirement lands in Phase 2.

Import boundary: adapter and LLM packages are imported lazily inside ingest/
summarize paths so ``run_render`` can be imported without pulling network/LLM
dependencies (D-20).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from pipeline.models import NormalizedItem
from pipeline.render.digest_json import emit_digest_json
from pipeline.render.html import render_digest
from pipeline.render.partition import AlsoCoveredMember, DigestCard
from pipeline.reporting.last_run import RunSummary, write_last_run_md
from pipeline.reporting.pipeline_report import build_pipeline_report, write_pipeline_report
from pipeline.week import parse_week_id, week_bounds
from store.db import (
    connect,
    delete_clusters_for_week,
    delete_ranks_for_week,
    delete_rollups_for_week,
    finalize_pipeline_run,
    get_canonical_item_ids_for_week,
    get_cluster_categories_for_week,
    get_cluster_members,
    get_clusters_for_week,
    get_existing_cluster_summary,
    get_existing_summary,
    get_item_by_source_external,
    get_items_for_week,
    get_last_known_cluster_category,
    get_pending_transcript_items,
    get_rank_positions_for_week,
    get_ranks_for_week,
    get_rollup,
    get_rollups_for_week,
    init_db,
    insert_cluster_ranks_batch,
    insert_cluster_summary,
    insert_item_summary,
    insert_pipeline_run,
    insert_weekly_rollup,
    ranks_cover_current_clusters,
    update_item_transcript,
    update_source_health,
    upsert_item,
    upsert_source,
)


def _utc_iso_now() -> str:
    """Second-precision ISO 8601 UTC timestamp (matches items.published_at format)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# Cloud-cron mode is signaled by an environment variable (set by the GHA
# workflow in .github/workflows/weekly-digest.yml). Manual local runs
# leave it unset so they never write a cron-complete marker.
CLOUD_CRON_MODE_ENV = "CLOUD_CRON_MODE"

# Markers directory inside the runner workspace (or local working tree).
# The workflow `rclone copy`-uploads this to the shared object-storage
# bucket's `markers/` path after the pipeline succeeds (D-B5b).
DEFAULT_MARKERS_DIR = Path("markers")


def write_cron_complete_marker(
    week_id: str,
    markers_dir: Path | str | None = None,
    *,
    now: datetime | None = None,
) -> Path:
    """Write ``markers/cron-complete-{week_id}.json`` (D-B5b).

    The cron-complete marker is the architectural seam between the cloud
    Sunday cron and the residential home worker (05-CONTEXT.md D-B5b):
    cron writes this file on success, then ``rclone copy``-uploads it to
    the shared object-storage bucket. The worker polls the bucket every
    ~10 minutes and, on finding a marker whose ``week_id`` matches the
    current calendar week, downloads the database, drains pending
    YouTube transcripts via ``--only-pending-transcripts``, commits the
    upgraded digest JSON, and deletes the marker (idempotency: a
    duplicate cycle finds no marker and exits).

    ``week_id`` is validated through :func:`pipeline.week.parse_week_id`
    so a malformed week id fails loudly rather than producing a marker
    the worker cannot match.

    Returns the path the marker was written to so the workflow can
    upload it without recomputing the filename.
    """
    parse_week_id(week_id)
    target_dir = Path(markers_dir) if markers_dir is not None else DEFAULT_MARKERS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    completed = (now or datetime.now(UTC)).astimezone(UTC)
    completed_iso = completed.strftime("%Y-%m-%dT%H:%M:%SZ")
    target = target_dir / f"cron-complete-{week_id}.json"
    payload = {"week_id": week_id, "completed_at": completed_iso}
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _maybe_write_cron_complete_marker(week_id: str, log) -> None:
    """Write the cron-complete marker only when ``CLOUD_CRON_MODE=1``.

    Local manual ``pipeline.run all`` invocations never set this env var,
    so a developer running the pipeline against the working tree does
    not produce a marker the home worker might pick up.
    """
    if os.environ.get(CLOUD_CRON_MODE_ENV) != "1":
        return
    try:
        path = write_cron_complete_marker(week_id)
        log.info("orchestrator.cron_complete_marker_written", path=str(path))
    except Exception as exc:  # pragma: no cover — best-effort; never break run_all
        log.warning(
            "orchestrator.cron_complete_marker_failed",
            error=type(exc).__name__,
            message=str(exc),
        )

if TYPE_CHECKING:
    from pipeline.budget import WeekBudget
    from pipeline.llm.summarize import SummaryResult

logger = structlog.get_logger(__name__)


@dataclass
class SourceRunStats:
    """Per-source ingest metrics for last_run.md."""

    source_id: str
    items_fetched: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class RunStats:
    week_id: str
    phase: str = ""
    started_at: datetime | None = None
    items_fetched: int = 0
    summaries_written: int = 0
    items_degraded: int = 0
    cost_usd_estimate: float = 0.0
    llm_calls: int = 0
    clusters_created: int = 0
    items_clustered: int = 0
    categorize_llm_calls: int = 0
    rank_llm_calls: int = 0
    rollup_llm_calls: int = 0
    rollup_cost_usd: float = 0.0
    summarize_cost_usd: float = 0.0
    categorize_cost_usd: float = 0.0
    rank_cost_usd: float = 0.0
    errors: list[dict[str, str]] = field(default_factory=list)
    out_path: Path | None = None
    digest_json_path: Path | None = None
    source_stats: dict[str, SourceRunStats] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.started_at is None:
            self.started_at = datetime.now(UTC)


def _pick_adapter(source_type: str):
    """Adapter registry — discriminated-union dispatch (D-00d, D-36)."""
    if source_type == "rss":
        from pipeline.adapters.rss import RssAdapter

        return RssAdapter()
    if source_type == "youtube":
        from pipeline.adapters.youtube import YoutubeAdapter

        return YoutubeAdapter()
    raise ValueError(f"no adapter registered for source type {source_type!r}")


def _append_ingest_error(
    stats: RunStats,
    src_stats: SourceRunStats,
    *,
    source_id: str,
    category: str,
    message: str,
    http_status: int | None = None,
) -> None:
    """Append a D-39 categorized error to both RunStats and per-source stats.

    The legacy ``error`` key is preserved alongside the typed ``category`` so
    Phase 1 callers and tests that grep messages still work; future surfaces
    (Phase 3+) should read ``category``.
    """
    src_stats.errors.append(message)
    entry: dict[str, str] = {
        "phase": "ingest",
        "source_id": source_id,
        "category": category,
        "message": message,
        "error": message,
    }
    if http_status is not None:
        entry["http_status"] = str(http_status)
    stats.errors.append(entry)


def _ingest(
    sources,
    conn,
    log,
    stats: RunStats,
    *,
    week_id: str | None = None,
    week_bounds_iso: tuple[str, str] | None = None,
) -> list[NormalizedItem]:
    """Fetch every enabled source; per-source try/except keeps the run alive.

    D-40: each iteration ends with a single ``update_source_health`` call that
    writes ``last_success_at`` (on successful fetch), ``last_item_at`` (when
    items entered the week window), and ``last_error_category`` (cleared to
    NULL on success).

    D-41: a successful fetch with zero items inside ``week_bounds_iso`` is
    recorded as ``category=empty_feed`` in ``RunStats.errors`` but does **not**
    abort the run or block downstream sources. ``last_success_at`` still
    advances because the HTTP+parse path worked. Circuit-breaker retry/backoff
    layered on top is D-42 → Phase 5.
    """
    from pipeline.adapters.base import FetchError

    week_start_iso, week_end_iso = week_bounds_iso or ("", "")

    all_items: list[NormalizedItem] = []
    for source in sources:
        upsert_source(conn, source)
        src_stats = stats.source_stats.setdefault(
            source.id, SourceRunStats(source_id=source.id)
        )
        log.info("ingest_fetch_start", source_id=source.id)
        t0 = time.perf_counter()
        try:
            adapter = _pick_adapter(source.type)
            fetched = adapter.fetch(source)
            http_status = getattr(adapter, "last_http_status", None)
        except FetchError as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            log.error(
                "ingest_fetch_complete",
                source_id=source.id,
                duration_ms=duration_ms,
                http_status=exc.http_status,
                items_count=0,
                error=type(exc).__name__,
                category=exc.category,
                message=str(exc),
            )
            _append_ingest_error(
                stats,
                src_stats,
                source_id=source.id,
                category=exc.category,
                message=f"{type(exc).__name__}: {exc}",
                http_status=exc.http_status,
            )
            update_source_health(conn, source.id, last_error_category=exc.category)
            continue
        except Exception as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            log.error(
                "ingest_fetch_complete",
                source_id=source.id,
                duration_ms=duration_ms,
                http_status=None,
                items_count=0,
                error=type(exc).__name__,
                category="adapter_internal",
                message=str(exc),
            )
            _append_ingest_error(
                stats,
                src_stats,
                source_id=source.id,
                category="adapter_internal",
                message=f"{type(exc).__name__}: {exc}",
            )
            update_source_health(conn, source.id, last_error_category="adapter_internal")
            continue

        duration_ms = int((time.perf_counter() - t0) * 1000)
        log.info(
            "ingest_fetch_complete",
            source_id=source.id,
            duration_ms=duration_ms,
            http_status=http_status,
            items_count=len(fetched),
        )
        src_stats.items_fetched = len(fetched)

        in_window_count = 0
        for item in fetched:
            existing = get_item_by_source_external(
                conn, item.source_id, item.external_id
            )
            try:
                item_id = upsert_item(conn, item)
            except Exception as exc:
                log.warning(
                    "ingest.upsert.failed",
                    source_id=source.id,
                    title=item.title,
                    error=str(exc),
                )
                _append_ingest_error(
                    stats,
                    src_stats,
                    source_id=source.id,
                    category="adapter_internal",
                    message=f"upsert: {exc}",
                )
                continue
            if week_start_iso and week_end_iso:
                item_iso = item.published_at_iso()
                if week_start_iso <= item_iso <= week_end_iso:
                    in_window_count += 1
                    if week_id and existing is not None:
                        _apply_cascade_for_item(
                            conn,
                            week_id=week_id,
                            item_id=item_id,
                            old_hash=existing["content_hash"],
                            new_hash=item.content_hash,
                            old_title=existing["title"],
                            new_title=item.title,
                            log=log,
                        )

        # D-41: empty_feed only when the fetch succeeded but yielded zero items
        # in the week window. The contract is non-fatal — we still record the
        # success on last_success_at so source-health tracking continues.
        if week_start_iso and week_end_iso and in_window_count == 0:
            _append_ingest_error(
                stats,
                src_stats,
                source_id=source.id,
                category="empty_feed",
                message=(
                    f"source returned {len(fetched)} items but zero fell in "
                    f"{week_start_iso}..{week_end_iso}"
                ),
            )

        now_iso = _utc_iso_now()
        update_source_health(
            conn,
            source.id,
            last_success_at=now_iso,
            last_item_at=now_iso if in_window_count > 0 else None,
            last_error_category="",  # clear on successful fetch
        )

        all_items.extend(fetched)
    conn.commit()
    stats.items_fetched = len(all_items)
    return all_items


def _dedup_week(
    *, week_id: str, week_start: datetime, week_end: datetime, conn, log, stats: RunStats
) -> int:
    """Deterministic dedup stage — rebuild clusters for the ISO week (D-67)."""
    from pipeline.dedup.cluster import run_dedup_for_week

    del week_start, week_end  # week bounds resolved inside cluster engine
    return run_dedup_for_week(
        week_id=week_id,
        conn=conn,
        log=log,
        stats=stats,
        fetch_redirects=False,
    )


def _summarize_week_items(
    *,
    week_id: str,
    week_start: datetime,
    week_end: datetime,
    conn,
    log,
    stats: RunStats,
    budget: WeekBudget | None = None,
) -> dict[str, SummaryResult]:
    """Summarize items in [week_start, week_end] missing a current summary."""
    from pipeline.budget import META_STAGE_ESTIMATE_USD
    from pipeline.llm.summarize import GeminiKeyMissing, SummaryResult, summarize_item

    rows = get_items_for_week(
        conn,
        week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    canonical_ids = get_canonical_item_ids_for_week(conn, week_id)
    if not canonical_ids:
        canonical_ids = {row["item_id"] for row in rows}

    estimate_per_item = (
        budget.baseline_per_item_usd if budget is not None else 0.001
    )

    summaries: dict[str, SummaryResult] = {}
    for row in rows:
        item_id = row["item_id"]
        if item_id not in canonical_ids:
            continue
        existing = get_existing_summary(conn, item_id, week_id, "summarize_v1")
        if existing is not None:
            existing_status = (
                existing["summary_status"]
                if "summary_status" in existing.keys() and existing["summary_status"]
                else "ok"
            )
            summaries[item_id] = SummaryResult(
                tldr=existing["tldr"],
                summary_confidence=existing["summary_confidence"],
                prompt_version=existing["prompt_version"],
                model_id=existing["model_id"],
                input_tokens=existing["input_tokens"],
                output_tokens=existing["output_tokens"],
                cost_usd_estimate=existing["cost_usd_estimate"],
                summary_input_truncated=bool(
                    existing["summary_input_truncated"]
                    if "summary_input_truncated" in existing.keys()
                    else 0
                ),
                summary_status=existing_status,
            )
            continue

        if budget is not None and not budget.can_afford(
            estimate_per_item, stage="summarize"
        ):
            budget.halt_if_over_cap(stage="summarize")
            log.warning(
                "budget.summarize_halted",
                spent_usd=budget.spent_usd,
                cap_usd=budget.cap_usd,
            )
            break

        try:
            log.info(
                "summarize_start",
                item_id=item_id,
                source_id=row["source_id"],
            )
            result = summarize_item(
                title=row["title"],
                publisher=row["publisher"],
                raw_content=row["raw_content"] or "",
                canonical_url=row["canonical_url"],
                item_id=item_id,
                source_id=row["source_id"],
            )
        except GeminiKeyMissing as exc:
            log.error("summarize.key_missing", error=str(exc))
            stats.errors.append(
                {
                    "phase": "summarize",
                    "item_id": item_id,
                    "error": "GEMINI_API_KEY not set",
                }
            )
            return summaries

        log.info(
            "summarize_complete",
            item_id=item_id,
            source_id=row["source_id"],
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd_estimate=result.cost_usd_estimate,
            summary_confidence=result.summary_confidence,
        )
        if result.input_tokens is not None or result.output_tokens is not None:
            stats.llm_calls += 1

        insert_item_summary(
            conn,
            item_id=item_id,
            week_id=week_id,
            tldr=result.tldr,
            summary_confidence=result.summary_confidence,
            prompt_version=result.prompt_version,
            model_id=result.model_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd_estimate=result.cost_usd_estimate,
            summary_input_truncated=result.summary_input_truncated,
            summary_status=result.summary_status,
        )
        summaries[item_id] = result

        if result.summary_confidence == "unavailable":
            stats.items_degraded += 1
        else:
            stats.summaries_written += 1
        if result.cost_usd_estimate is not None:
            stats.cost_usd_estimate += result.cost_usd_estimate
            stats.summarize_cost_usd += result.cost_usd_estimate
            if budget is not None:
                budget.record_spend(result.cost_usd_estimate, stage="summarize")

    conn.commit()
    return summaries


def _source_tags_by_id(conn) -> dict[str, str | None]:
    """Map source_id → YAML tag for categorize fallback (D-48, D-49)."""
    from pipeline.config import load_sources

    tags: dict[str, str | None] = {}
    for source in load_sources():
        tags[source.id] = source.tag
    rows = conn.execute("SELECT source_id, tag FROM sources").fetchall()
    for row in rows:
        if row["source_id"] not in tags:
            tags[row["source_id"]] = row["tag"]
    return tags


def _categorize_week_clusters(
    *, week_id: str, conn, log, stats: RunStats, budget: WeekBudget | None = None
) -> None:
    """Item-level categorize checkpoint — skip rows already persisted (D-67)."""
    from pipeline.budget import META_STAGE_ESTIMATE_USD
    from pipeline.llm.categorize import PROMPT_VERSION, categorize_cluster
    from pipeline.llm.summarize import GeminiKeyMissing

    if budget is not None and not budget.meta_stages_allowed():
        log.info("categorize.skipped_budget")
        return

    clusters = get_clusters_for_week(conn, week_id)
    if not clusters:
        log.info("categorize.no_clusters")
        return

    source_tags = _source_tags_by_id(conn)

    for cluster in clusters:
        cluster_id = cluster["cluster_id"]
        existing = get_existing_cluster_summary(
            conn, cluster_id, week_id, PROMPT_VERSION
        )
        if existing is not None:
            continue

        item_row = conn.execute(
            "SELECT * FROM items WHERE item_id = ?",
            (cluster["canonical_item_id"],),
        ).fetchone()
        if item_row is None:
            log.warning(
                "categorize.missing_canonical_item",
                cluster_id=cluster_id,
                item_id=cluster["canonical_item_id"],
            )
            continue

        summary_row = get_existing_summary(
            conn, item_row["item_id"], week_id, "summarize_v1"
        )
        summary_text = (summary_row["tldr"] if summary_row else None) or ""
        source_tag = source_tags.get(item_row["source_id"])
        last_known = get_last_known_cluster_category(
            conn, cluster_id, exclude_prompt_version=PROMPT_VERSION
        )

        if budget is not None and not budget.can_afford(
            META_STAGE_ESTIMATE_USD, stage="categorize"
        ):
            log.warning("budget.categorize_halted")
            budget.halt_if_over_cap(stage="categorize")
            return

        try:
            log.info("categorize_start", cluster_id=cluster_id)
            result = categorize_cluster(
                title=item_row["title"],
                summary_text=summary_text,
                source_tag=source_tag,
                cluster_id=cluster_id,
                last_known_category=last_known,  # type: ignore[arg-type]
            )
        except GeminiKeyMissing as exc:
            log.error("categorize.key_missing", error=str(exc))
            stats.errors.append(
                {
                    "phase": "categorize",
                    "error": "GEMINI_API_KEY not set",
                }
            )
            return

        if result.input_tokens is not None or result.output_tokens is not None:
            stats.categorize_llm_calls += 1
            stats.llm_calls += 1

        insert_cluster_summary(
            conn,
            cluster_id=cluster_id,
            week_id=week_id,
            category=result.category,
            category_confidence=result.category_confidence,
            category_status=result.category_status,
            prompt_version=result.prompt_version,
            model_id=result.model_id,
        )
        if result.cost_usd_estimate is not None:
            stats.cost_usd_estimate += result.cost_usd_estimate
            stats.categorize_cost_usd += result.cost_usd_estimate
            if budget is not None:
                budget.record_spend(result.cost_usd_estimate, stage="categorize")

        conn.commit()


def _load_cluster_rank_inputs(conn, week_id: str) -> list:
    """Build rank prompt inputs from categorized clusters with summaries."""
    from pipeline.llm.categorize import PROMPT_VERSION as CATEGORIZE_VERSION
    from pipeline.llm.rank import ClusterRankInput

    clusters = get_clusters_for_week(conn, week_id)
    if not clusters:
        return []

    inputs: list[ClusterRankInput] = []
    for cluster in clusters:
        cluster_id = cluster["cluster_id"]
        summary_row = get_existing_cluster_summary(
            conn, cluster_id, week_id, CATEGORIZE_VERSION
        )
        category = summary_row["category"] if summary_row else "technical"

        item_row = conn.execute(
            "SELECT * FROM items WHERE item_id = ?",
            (cluster["canonical_item_id"],),
        ).fetchone()
        if item_row is None:
            continue

        tldr_row = get_existing_summary(
            conn, item_row["item_id"], week_id, "summarize_v1"
        )
        summary_text = (tldr_row["tldr"] if tldr_row else None) or ""
        published_at = datetime.fromisoformat(
            item_row["published_at"].replace("Z", "+00:00")
        )
        inputs.append(
            ClusterRankInput(
                cluster_id=cluster_id,
                category=category,
                title=item_row["title"],
                summary_text=summary_text,
                published_at=published_at,
            )
        )
    return inputs


def _rank_week(
    *, week_id: str, conn, log, stats: RunStats, budget: WeekBudget | None = None
) -> None:
    """Stage-level rank checkpoint — single LLM call per week (D-67)."""
    from pipeline.budget import META_STAGE_ESTIMATE_USD
    from pipeline.llm.rank import PROMPT_VERSION, rank_week_clusters
    from pipeline.llm.summarize import GeminiKeyMissing

    if budget is not None and not budget.meta_stages_allowed():
        log.info("rank.skipped_budget")
        return

    existing = get_ranks_for_week(conn, week_id, PROMPT_VERSION)
    if existing:
        if ranks_cover_current_clusters(conn, week_id, PROMPT_VERSION):
            log.info("rank.skip_existing", count=len(existing))
            return
        log.info("rank.stale_checkpoint", count=len(existing))
        delete_ranks_for_week(conn, week_id, PROMPT_VERSION)

    cluster_inputs = _load_cluster_rank_inputs(conn, week_id)
    if not cluster_inputs:
        log.info("rank.no_clusters")
        return

    if budget is not None and not budget.can_afford(
        META_STAGE_ESTIMATE_USD, stage="rank"
    ):
        log.warning("budget.rank_halted")
        budget.halt_if_over_cap(stage="rank")
        return

    try:
        log.info("rank_start", cluster_count=len(cluster_inputs))
        results = rank_week_clusters(week_id=week_id, clusters=cluster_inputs)
    except GeminiKeyMissing as exc:
        log.error("rank.key_missing", error=str(exc))
        stats.errors.append(
            {
                "phase": "rank",
                "error": "GEMINI_API_KEY not set",
            }
        )
        return

    if results and results[0].rank_status == "ok":
        if results[0].input_tokens is not None or results[0].output_tokens is not None:
            stats.rank_llm_calls += 1
            stats.llm_calls += 1

    insert_cluster_ranks_batch(
        conn,
        week_id=week_id,
        rows=[
            {
                "cluster_id": row.cluster_id,
                "rank_score": row.rank_score,
                "rank_position": row.rank_position,
                "rank_status": row.rank_status,
                "prompt_version": row.prompt_version,
                "model_id": row.model_id,
            }
            for row in results
        ],
    )
    for row in results:
        if row.cost_usd_estimate is not None:
            stats.cost_usd_estimate += row.cost_usd_estimate
            stats.rank_cost_usd += row.cost_usd_estimate
            if budget is not None:
                budget.record_spend(row.cost_usd_estimate, stage="rank")

    conn.commit()


def _load_cluster_rollup_inputs_by_category(
    conn, week_id: str
) -> dict[str, list]:
    """Build per-category ranked cluster inputs for mini rollups."""
    from pipeline.llm.categorize import PROMPT_VERSION as CATEGORIZE_VERSION
    from pipeline.llm.rank import PROMPT_VERSION as RANK_VERSION
    from pipeline.llm.rollup import ClusterRollupInput

    clusters = get_clusters_for_week(conn, week_id)
    if not clusters:
        return {}

    rank_rows = {
        row["cluster_id"]: row
        for row in get_ranks_for_week(conn, week_id, RANK_VERSION)
    }
    by_category: dict[str, list[ClusterRollupInput]] = {
        "edtech": [],
        "business": [],
        "technical": [],
    }

    for cluster in clusters:
        cluster_id = cluster["cluster_id"]
        rank_row = rank_rows.get(cluster_id)
        if rank_row is None:
            continue

        summary_row = get_existing_cluster_summary(
            conn, cluster_id, week_id, CATEGORIZE_VERSION
        )
        if summary_row is None:
            continue
        category = summary_row["category"]
        if category not in by_category:
            continue

        item_row = conn.execute(
            "SELECT * FROM items WHERE item_id = ?",
            (cluster["canonical_item_id"],),
        ).fetchone()
        if item_row is None:
            continue

        tldr_row = get_existing_summary(
            conn, item_row["item_id"], week_id, "summarize_v1"
        )
        summary_text = (tldr_row["tldr"] if tldr_row else None) or ""
        by_category[category].append(
            ClusterRollupInput(
                cluster_id=cluster_id,
                title=item_row["title"],
                summary_text=summary_text,
                rank_position=int(rank_row["rank_position"]),
            )
        )

    return by_category


def _record_rollup_result(
    conn,
    *,
    week_id: str,
    scope: str,
    result,
    stats: RunStats,
    budget: WeekBudget | None = None,
) -> None:
    """Persist one rollup row and update RunStats counters."""
    if result.input_tokens is not None or result.output_tokens is not None:
        stats.rollup_llm_calls += 1
        stats.llm_calls += 1
    insert_weekly_rollup(
        conn,
        week_id=week_id,
        scope=scope,
        narrative_md=result.narrative_md,
        rollup_status=result.rollup_status,
        prompt_version=result.prompt_version,
        model_id=result.model_id,
        input_token_count=result.input_tokens,
        output_token_count=result.output_tokens,
        cost_usd_estimate=result.cost_usd_estimate,
    )
    if result.cost_usd_estimate is not None:
        stats.cost_usd_estimate += result.cost_usd_estimate
        stats.rollup_cost_usd += result.cost_usd_estimate
        if budget is not None:
            budget.record_spend(result.cost_usd_estimate, stage="rollup")


def _rollup_week(
    *, week_id: str, conn, log, stats: RunStats, budget: WeekBudget | None = None
) -> None:
    """Stage-level rollup checkpoint — up to five LLM calls per week (D-67)."""
    from pipeline.budget import META_STAGE_ESTIMATE_USD
    from pipeline.llm.rank import PROMPT_VERSION as RANK_VERSION
    from pipeline.llm.rollup import (
        CATEGORY_ORDER,
        CATEGORY_PROMPT_VERSION,
        WEEKLY_PROMPT_VERSION,
        rollup_category,
        rollup_weekly,
        scope_for_category,
    )
    from pipeline.llm.summarize import GeminiKeyMissing

    if budget is not None and not budget.meta_stages_allowed():
        log.info("rollup.skipped_budget")
        return

    by_category = _load_cluster_rollup_inputs_by_category(conn, week_id)
    mini_paragraphs: dict[str, str] = {}

    for category in CATEGORY_ORDER:
        scope = scope_for_category(category)
        existing = get_rollup(conn, week_id, scope, CATEGORY_PROMPT_VERSION)
        if existing:
            if ranks_cover_current_clusters(conn, week_id, RANK_VERSION):
                if existing["rollup_status"] == "ok" and existing["narrative_md"]:
                    mini_paragraphs[category] = existing["narrative_md"]
                log.info("rollup_category.skip_existing", scope=scope)
                continue
            log.info("rollup.stale_checkpoint", scope=scope)
            conn.execute(
                """
                DELETE FROM weekly_rollups
                 WHERE week_id = ? AND scope = ? AND prompt_version = ?
                """,
                (week_id, scope, CATEGORY_PROMPT_VERSION),
            )

        clusters = by_category.get(category, [])
        if not clusters:
            log.info("rollup_category.no_clusters", category=category)
            continue

        if budget is not None and not budget.can_afford(
            META_STAGE_ESTIMATE_USD, stage="rollup"
        ):
            log.warning("budget.rollup_halted", scope=scope)
            budget.halt_if_over_cap(stage="rollup")
            return

        try:
            log.info(
                "rollup_category_start",
                category=category,
                cluster_count=len(clusters),
            )
            result = rollup_category(
                week_id=week_id,
                category=category,
                clusters=clusters,
            )
        except GeminiKeyMissing as exc:
            log.error("rollup.key_missing", error=str(exc))
            stats.errors.append(
                {
                    "phase": "rollup",
                    "error": "GEMINI_API_KEY not set",
                }
            )
            return

        _record_rollup_result(
            conn,
            week_id=week_id,
            scope=scope,
            result=result,
            stats=stats,
            budget=budget,
        )
        if result.rollup_status == "ok" and result.narrative_md:
            mini_paragraphs[category] = result.narrative_md

    existing_weekly = get_rollup(conn, week_id, "weekly", WEEKLY_PROMPT_VERSION)
    if existing_weekly and ranks_cover_current_clusters(conn, week_id, RANK_VERSION):
        log.info("rollup_weekly.skip_existing")
    else:
        if existing_weekly:
            log.info("rollup.stale_checkpoint", scope="weekly")
            conn.execute(
                """
                DELETE FROM weekly_rollups
                 WHERE week_id = ? AND scope = 'weekly' AND prompt_version = ?
                """,
                (week_id, WEEKLY_PROMPT_VERSION),
            )
        if budget is not None and not budget.can_afford(
            META_STAGE_ESTIMATE_USD, stage="rollup"
        ):
            log.warning("budget.rollup_weekly_halted")
            budget.halt_if_over_cap(stage="rollup")
            return
        try:
            log.info("rollup_weekly_start")
            weekly_result = rollup_weekly(
                week_id=week_id,
                mini_paragraphs=mini_paragraphs,  # type: ignore[arg-type]
            )
        except GeminiKeyMissing as exc:
            log.error("rollup.key_missing", error=str(exc))
            stats.errors.append(
                {
                    "phase": "rollup",
                    "error": "GEMINI_API_KEY not set",
                }
            )
            return

        _record_rollup_result(
            conn,
            week_id=week_id,
            scope="weekly",
            result=weekly_result,
            stats=stats,
            budget=budget,
        )

    conn.commit()


def _row_get(row, column: str, default=None):
    """Sqlite3.Row.get-style helper — Row has no .get() in Python's sqlite3."""
    try:
        return row[column]
    except (IndexError, KeyError):
        return default


def _source_type_for(row) -> str:
    """Best-effort source_type lookup; defaults to 'rss' so missing JOINs degrade safely."""
    val = _row_get(row, "source_type") or _row_get(row, "type")
    return str(val) if val else "rss"


def _infer_summary_status(
    *,
    persisted_status: str | None,
    tldr: str | None,
    summary_confidence: str,
    transcript_status: str | None,
) -> str:
    """Derive ``summary_status`` for cards built from rows that don't carry one.

    Modern rows from plan 02-04+ carry a real ``summary_status`` and we
    return it as-is. Older rows have ``summary_status IS NULL``; we infer
    a status so the renderer routes them correctly per LOCKED-01:

    * tldr present                                  → ``ok`` (main feed)
    * transcript_status in {pending_local, missing} → ``transcript_missing``
                                                       (main feed, in-place
                                                       degraded card)
    * summary_confidence == 'unavailable'           → ``thin`` (footer)
    * fallback                                      → ``thin`` (footer)

    The 2026-05-23 LOCKED-01 refinement narrowed the footer to RSS-thin
    only. YouTube items whose transcripts haven't fetched yet now route to
    the in-place degraded bucket so the reader sees the title + link in
    context with the rest of the week's items, not buried in the footer.
    """
    if persisted_status:
        return persisted_status
    if tldr and tldr.strip():
        return "ok"
    if transcript_status in {"pending_local", "missing"}:
        return "transcript_missing"
    if summary_confidence == "unavailable":
        return "thin"
    return "thin"


def _also_covered_for_item(conn, *, week_id: str, item_id: str) -> tuple[AlsoCoveredMember, ...]:
    """Load non-canonical member attributions for a canonical card (D-64)."""
    cluster_row = conn.execute(
        """
        SELECT cluster_id FROM story_clusters
         WHERE week_id = ? AND canonical_item_id = ?
        """,
        (week_id, item_id),
    ).fetchone()
    if cluster_row is None:
        return ()
    members = get_cluster_members(conn, cluster_row["cluster_id"])
    if len(members) <= 1:
        return ()
    attributions = [
        AlsoCoveredMember(display_name=member["display_name"], url=member["canonical_url"])
        for member in members
        if not member["is_canonical"]
    ]
    attributions.sort(key=lambda member: member.display_name.lower())
    return tuple(attributions)


def _build_card_from_row(
    row,
    *,
    tldr: str | None,
    summary_confidence: str,
    summary_status: str | None,
    source_type: str | None = None,
    also_covered: tuple[AlsoCoveredMember, ...] = (),
    category: str | None = None,
    rank_position: int | None = None,
) -> DigestCard:
    """Shared card factory used by both LLM and DB-only render paths."""
    resolved_source_type = source_type or _source_type_for(row)
    transcript_status = _row_get(row, "transcript_status")
    effective_status = _infer_summary_status(
        persisted_status=summary_status,
        tldr=tldr,
        summary_confidence=summary_confidence,
        transcript_status=transcript_status,
    )
    return DigestCard(
        title=row["title"],
        publisher=row["publisher"],
        canonical_url=row["canonical_url"],
        published_at=datetime.fromisoformat(row["published_at"].replace("Z", "+00:00")),
        tldr=tldr,
        summary_confidence=summary_confidence,
        source_type=resolved_source_type,
        transcript_status=transcript_status,
        summary_status=effective_status,
        also_covered=also_covered,
        category=category,
        rank_position=rank_position,
        channel_url=_row_get(row, "channel_url"),
    )


def _canonical_rows_for_render(
    conn,
    rows,
    *,
    week_id: str,
) -> list:
    """Keep only canonical cluster representatives (one card per story)."""
    canonical_ids = get_canonical_item_ids_for_week(conn, week_id)
    if not canonical_ids:
        return list(rows)
    return [row for row in rows if row["item_id"] in canonical_ids]


def _build_cards(
    conn,
    *,
    week_id: str,
    rows,
    summaries: dict[str, SummaryResult],
) -> list[DigestCard]:
    """Turn item rows + summaries into render-ready cards (newest first)."""
    category_map = get_cluster_categories_for_week(conn, week_id)
    rank_map = get_rank_positions_for_week(conn, week_id)
    cards: list[DigestCard] = []
    for row in rows:
        result = summaries.get(row["item_id"])
        also_covered = _also_covered_for_item(conn, week_id=week_id, item_id=row["item_id"])
        cards.append(
            _build_card_from_row(
                row,
                tldr=result.tldr if result else None,
                summary_confidence=result.summary_confidence if result else "unavailable",
                summary_status=result.summary_status if result else None,
                also_covered=also_covered,
                category=category_map.get(row["item_id"]),
                rank_position=rank_map.get(row["item_id"]),
            )
        )
    cards.sort(key=lambda c: c.published_at, reverse=True)
    return cards


def _build_cards_from_db(conn, rows, week_id: str) -> list[DigestCard]:
    """Build render cards from SQLite only — no LLM (D-20 render path)."""
    category_map = get_cluster_categories_for_week(conn, week_id)
    rank_map = get_rank_positions_for_week(conn, week_id)
    cards: list[DigestCard] = []
    for row in rows:
        existing = get_existing_summary(
            conn, row["item_id"], week_id, "summarize_v1"
        )
        also_covered = _also_covered_for_item(conn, week_id=week_id, item_id=row["item_id"])
        cards.append(
            _build_card_from_row(
                row,
                tldr=existing["tldr"] if existing else None,
                summary_confidence=(
                    existing["summary_confidence"] if existing else "unavailable"
                ),
                summary_status=(
                    _row_get(existing, "summary_status") if existing else None
                ),
                also_covered=also_covered,
                category=category_map.get(row["item_id"]),
                rank_position=rank_map.get(row["item_id"]),
            )
        )
    cards.sort(key=lambda c: c.published_at, reverse=True)
    return cards


def _pipeline_notice_counts(
    *, cards: list[DigestCard], stats: RunStats
) -> tuple[int, int]:
    """D-26 inputs: pending-local card count + non-empty_feed fetch failure count.

    D-41 explicitly excludes ``empty_feed`` from the failed-source clause —
    a source that simply published nothing inside the week window is not
    "failed" from the reader's perspective.
    """
    pending = sum(1 for c in cards if c.transcript_status == "pending_local")
    failed_sources = sum(
        1
        for err in stats.errors
        if err.get("phase") == "ingest"
        and err.get("category") not in (None, "empty_feed")
    )
    return pending, failed_sources


def _count_pending_summarize(
    conn,
    *,
    week_id: str,
    week_start: datetime,
    week_end: datetime,
) -> int:
    """Items in the week window that still need a summarize_v1 row."""
    rows = get_items_for_week(
        conn,
        week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    canonical_ids = get_canonical_item_ids_for_week(conn, week_id)
    if not canonical_ids:
        canonical_ids = {row["item_id"] for row in rows}
    pending = 0
    for row in rows:
        if row["item_id"] not in canonical_ids:
            continue
        if get_existing_summary(conn, row["item_id"], week_id, "summarize_v1") is None:
            pending += 1
    return pending


def _apply_cascade_for_item(
    conn,
    *,
    week_id: str,
    item_id: str,
    old_hash: str | None,
    new_hash: str,
    log,
    old_title: str | None = None,
    new_title: str | None = None,
    force_rebuild_clusters: bool = False,
    force_rebuild_rollup: bool = False,
) -> set[str]:
    """Invalidate downstream artifacts when ``content_hash`` or title changes (D-68)."""
    from pipeline.cascade import (
        STAGE_DEDUP,
        STAGE_RANK,
        STAGE_ROLLUP,
        STAGE_SUMMARIZE,
        plan_invalidation,
    )
    from pipeline.dedup.title_fuzzy import normalize_title

    cluster_row = conn.execute(
        """
        SELECT cluster_id FROM story_clusters
         WHERE week_id = ? AND canonical_item_id = ?
        """,
        (week_id, item_id),
    ).fetchone()
    is_canonical = cluster_row is not None

    if old_title is not None and new_title is not None:
        title_changed = normalize_title(old_title) != normalize_title(new_title)
    else:
        title_changed = False

    stages = plan_invalidation(
        item_id=item_id,
        old_hash=old_hash,
        new_hash=new_hash,
        is_canonical=is_canonical,
        title_changed=title_changed,
        force_rebuild_clusters=force_rebuild_clusters,
        force_rebuild_rollup=force_rebuild_rollup,
    )
    if STAGE_SUMMARIZE in stages:
        conn.execute(
            "DELETE FROM item_summaries WHERE item_id = ? AND week_id = ?",
            (item_id, week_id),
        )
    if STAGE_DEDUP in stages:
        delete_clusters_for_week(conn, week_id)
    if STAGE_RANK in stages:
        conn.execute("DELETE FROM cluster_ranks WHERE week_id = ?", (week_id,))
    if STAGE_ROLLUP in stages:
        delete_rollups_for_week(conn, week_id)
    if stages:
        log.info("cascade.planned", item_id=item_id, stages=sorted(stages))
    return stages


def _write_last_run(
    stats: RunStats, *, status: str, budget: WeekBudget | None = None
) -> None:
    """Persist out/last_run.md for debugging (D-08)."""
    per_source = [
        (sid, s.items_fetched, s.errors)
        for sid, s in sorted(stats.source_stats.items())
    ]
    write_last_run_md(
        RunSummary(
            week_id=stats.week_id,
            phase=stats.phase,
            started_at=stats.started_at,
            finished_at=datetime.now(UTC),
            status=status,
            items_fetched=stats.items_fetched,
            summaries_written=stats.summaries_written,
            items_degraded=stats.items_degraded,
            llm_calls=stats.llm_calls,
            cost_usd_estimate=stats.cost_usd_estimate,
            clusters_created=stats.clusters_created,
            items_clustered=stats.items_clustered,
            categorize_llm_calls=stats.categorize_llm_calls,
            rank_llm_calls=stats.rank_llm_calls,
            rollup_llm_calls=stats.rollup_llm_calls,
            budget_spent_usd=budget.spent_usd if budget else stats.cost_usd_estimate,
            budget_halted=budget.halted if budget else False,
            per_source=per_source,
            errors=stats.errors,
            out_path=stats.out_path,
        )
    )


def _finalize(
    conn,
    run_id: str,
    stats: RunStats,
    *,
    phase: str,
    budget: WeekBudget | None = None,
    out_dir: Path | None = None,
) -> None:
    status = "success" if not stats.errors else "partial"
    if budget is not None and budget.halted:
        status = "partial"
    finalize_pipeline_run(
        conn,
        run_id,
        status=status,
        items_fetched=stats.items_fetched,
        summaries_written=stats.summaries_written,
        items_degraded=stats.items_degraded,
        cost_usd_estimate=stats.cost_usd_estimate,
        errors_json=json.dumps(stats.errors),
    )
    conn.commit()
    write_pipeline_report(
        conn,
        stats,
        run_id=run_id,
        status=status,
        budget=budget,
        out_dir=out_dir,
    )
    _write_last_run(stats, status=status, budget=budget)
    logger.info(
        "orchestrator.complete",
        phase=phase,
        week_id=stats.week_id,
        status=status,
        items_fetched=stats.items_fetched,
        summaries_written=stats.summaries_written,
        items_degraded=stats.items_degraded,
        cost_usd_estimate=round(stats.cost_usd_estimate, 6),
        out_path=str(stats.out_path) if stats.out_path else None,
    )


def _ingest_pending_transcripts(
    conn,
    log,
    stats: RunStats,
    *,
    week_id: str | None = None,
    force_rebuild_clusters: bool = False,
    force_rebuild_rollup: bool = False,
) -> int:
    """D-23 local catch-up: re-fetch transcripts for ``pending_local`` items.

    Returns the count of items whose ``transcript_status`` flipped (ok or
    missing). Network/proxy errors leave items at ``pending_local`` so the
    next catch-up attempt can pick them up. Per-item failures never abort the
    loop — one bad video should not block the rest.
    """
    from pipeline.adapters.youtube import YoutubeAdapter

    rows = get_pending_transcript_items(conn)
    if not rows:
        log.info("catch_up.no_pending_items")
        return 0

    adapter = YoutubeAdapter()
    flipped = 0
    for row in rows:
        external_id = row["external_id"]
        # external_id format: yt:video:{video_id} (plan 02-01 D-00c)
        if not external_id.startswith("yt:video:"):
            log.warning(
                "catch_up.skipped_non_youtube",
                item_id=row["item_id"],
                external_id=external_id,
            )
            continue
        video_id = external_id.split(":", 2)[-1]
        text, new_status = adapter.fetch_transcript(video_id, catch_up=True)
        if new_status == "pending_local":
            log.info(
                "catch_up.still_pending",
                item_id=row["item_id"],
                video_id=video_id,
            )
            continue

        # Recompute content_hash on successful flip — raw_content is the
        # source of truth for downstream summarize/dedup.
        from pipeline.models import hash_content

        raw_content = text if (text is not None and new_status == "ok") else None
        old_hash = row["content_hash"] if "content_hash" in row.keys() else None
        if raw_content is not None:
            new_hash = hash_content(raw_content)
            update_item_transcript(
                conn,
                row["item_id"],
                transcript_status=new_status,
                raw_content=raw_content,
            )
            conn.execute(
                "UPDATE items SET content_hash = ? WHERE item_id = ?",
                (new_hash, row["item_id"]),
            )
            if week_id is not None and old_hash != new_hash:
                _apply_cascade_for_item(
                    conn,
                    week_id=week_id,
                    item_id=row["item_id"],
                    old_hash=old_hash,
                    new_hash=new_hash,
                    old_title=row["title"],
                    new_title=row["title"],
                    log=log,
                    force_rebuild_clusters=force_rebuild_clusters,
                    force_rebuild_rollup=force_rebuild_rollup,
                )
        else:
            update_item_transcript(
                conn,
                row["item_id"],
                transcript_status=new_status,
            )
        flipped += 1
        log.info(
            "catch_up.flipped",
            item_id=row["item_id"],
            video_id=video_id,
            transcript_status=new_status,
        )

    conn.commit()
    stats.items_fetched = flipped
    return flipped


def run_ingest(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    only_pending_transcripts: bool = False,
) -> RunStats:
    """Fetch all enabled sources and upsert into SQLite (no week filter on fetch).

    D-23: ``only_pending_transcripts=True`` skips the standard adapter loop
    entirely and only retries transcript fetches for items previously left in
    ``transcript_status='pending_local'``. The catch-up path is the only one
    that may flip an item to ``missing`` (after a residential-IP confirmation
    that captions truly don't exist).
    """
    from pipeline.config import enabled_sources

    init_db(db_path)
    week_start, week_end = week_bounds(week_id)
    week_iso = (
        week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    log = logger.bind(week_id=week_id, only_pending_transcripts=only_pending_transcripts)
    stats = RunStats(week_id=week_id, phase="ingest")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="ingest")
        conn.commit()
        try:
            log.info("orchestrator.start", phase="ingest")
            if only_pending_transcripts:
                _ingest_pending_transcripts(conn, log, stats, week_id=week_id)
                _finalize(conn, run_id, stats, phase="ingest")
                return stats
            sources = enabled_sources()
            if not sources:
                log.warning("orchestrator.no_sources")
            _ingest(
                sources,
                conn,
                log,
                stats,
                week_id=week_id,
                week_bounds_iso=week_iso,
            )
            _finalize(conn, run_id, stats, phase="ingest")
            return stats
        except Exception as exc:
            log.error(
                "orchestrator.failed",
                phase="ingest",
                error=type(exc).__name__,
                message=str(exc),
            )
            stats.errors.append(
                {"phase": "ingest", "error": f"{type(exc).__name__}: {exc}"}
            )
            finalize_pipeline_run(
                conn,
                run_id,
                status="failed",
                items_fetched=stats.items_fetched,
                errors_json=json.dumps(stats.errors),
            )
            conn.commit()
            _write_last_run(stats, status="failed")
            raise


def run_dedup(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
    force_rebuild_clusters: bool = False,
) -> RunStats:
    """Cluster same-story items for ``week_id`` (deterministic, no LLM)."""
    init_db(db_path)
    week_start, week_end = week_bounds(week_id)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="dedup")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="dedup")
        conn.commit()
        try:
            log.info("orchestrator.start", phase="dedup")
            if force_rebuild_clusters:
                delete_clusters_for_week(conn, week_id)
                conn.commit()
            _dedup_week(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                conn=conn,
                log=log,
                stats=stats,
            )
            _finalize(conn, run_id, stats, phase="dedup", out_dir=out_dir)
            return stats
        except Exception as exc:
            log.error(
                "orchestrator.failed",
                phase="dedup",
                error=type(exc).__name__,
                message=str(exc),
            )
            stats.errors.append(
                {"phase": "dedup", "error": f"{type(exc).__name__}: {exc}"}
            )
            finalize_pipeline_run(
                conn,
                run_id,
                status="failed",
                errors_json=json.dumps(stats.errors),
            )
            conn.commit()
            _write_last_run(stats, status="failed")
            raise


def run_summarize(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
    max_cost_usd: float | None = None,
) -> RunStats:
    """Summarize items in the week window that lack a current summary."""
    from pipeline.budget import WeekBudget

    init_db(db_path)
    week_start, week_end = week_bounds(week_id)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="summarize")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="summarize")
        conn.commit()
        budget = WeekBudget.from_config(
            cap_override=max_cost_usd, conn=conn, week_id=week_id
        )
        pending = _count_pending_summarize(
            conn, week_id=week_id, week_start=week_start, week_end=week_end
        )
        budget.set_pre_flight(pending_summarize=pending)
        try:
            log.info("orchestrator.start", phase="summarize")
            _summarize_week_items(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                conn=conn,
                log=log,
                stats=stats,
                budget=budget,
            )
            _finalize(
                conn, run_id, stats, phase="summarize", budget=budget, out_dir=out_dir
            )
            return stats
        except Exception as exc:
            log.error(
                "orchestrator.failed",
                phase="summarize",
                error=type(exc).__name__,
                message=str(exc),
            )
            stats.errors.append(
                {"phase": "summarize", "error": f"{type(exc).__name__}: {exc}"}
            )
            finalize_pipeline_run(
                conn,
                run_id,
                status="failed",
                summaries_written=stats.summaries_written,
                items_degraded=stats.items_degraded,
                cost_usd_estimate=stats.cost_usd_estimate,
                errors_json=json.dumps(stats.errors),
            )
            conn.commit()
            _write_last_run(stats, status="failed")
            raise


def run_categorize(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
    max_cost_usd: float | None = None,
) -> RunStats:
    """Classify story clusters into edtech|business|technical."""
    from pipeline.budget import WeekBudget

    init_db(db_path)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="categorize")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="categorize")
        conn.commit()
        budget = WeekBudget.from_config(
            cap_override=max_cost_usd, conn=conn, week_id=week_id
        )
        try:
            log.info("orchestrator.start", phase="categorize")
            _categorize_week_clusters(
                week_id=week_id,
                conn=conn,
                log=log,
                stats=stats,
                budget=budget,
            )
            _finalize(
                conn,
                run_id,
                stats,
                phase="categorize",
                budget=budget,
                out_dir=out_dir,
            )
            return stats
        except Exception as exc:
            log.error(
                "orchestrator.failed",
                phase="categorize",
                error=type(exc).__name__,
                message=str(exc),
            )
            stats.errors.append(
                {"phase": "categorize", "error": f"{type(exc).__name__}: {exc}"}
            )
            finalize_pipeline_run(
                conn,
                run_id,
                status="failed",
                cost_usd_estimate=stats.cost_usd_estimate,
                errors_json=json.dumps(stats.errors),
            )
            conn.commit()
            _write_last_run(stats, status="failed")
            raise


def run_rank(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
    max_cost_usd: float | None = None,
) -> RunStats:
    """Rank story clusters for the week (single LLM call)."""
    from pipeline.budget import WeekBudget

    init_db(db_path)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="rank")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="rank")
        conn.commit()
        budget = WeekBudget.from_config(
            cap_override=max_cost_usd, conn=conn, week_id=week_id
        )
        try:
            log.info("orchestrator.start", phase="rank")
            _rank_week(
                week_id=week_id, conn=conn, log=log, stats=stats, budget=budget
            )
            _finalize(
                conn, run_id, stats, phase="rank", budget=budget, out_dir=out_dir
            )
            return stats
        except Exception as exc:
            log.error(
                "orchestrator.failed",
                phase="rank",
                error=type(exc).__name__,
                message=str(exc),
            )
            stats.errors.append(
                {"phase": "rank", "error": f"{type(exc).__name__}: {exc}"}
            )
            finalize_pipeline_run(
                conn,
                run_id,
                status="failed",
                cost_usd_estimate=stats.cost_usd_estimate,
                errors_json=json.dumps(stats.errors),
            )
            conn.commit()
            _write_last_run(stats, status="failed")
            raise


def run_rollup(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
    max_cost_usd: float | None = None,
    force_rebuild_rollup: bool = False,
) -> RunStats:
    """Run hierarchical weekly rollups (up to five LLM calls)."""
    from pipeline.budget import WeekBudget

    init_db(db_path)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="rollup")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="rollup")
        conn.commit()
        budget = WeekBudget.from_config(
            cap_override=max_cost_usd, conn=conn, week_id=week_id
        )
        try:
            log.info("orchestrator.start", phase="rollup")
            if force_rebuild_rollup:
                delete_rollups_for_week(conn, week_id)
                conn.commit()
            _rollup_week(
                week_id=week_id, conn=conn, log=log, stats=stats, budget=budget
            )
            _finalize(
                conn, run_id, stats, phase="rollup", budget=budget, out_dir=out_dir
            )
            return stats
        except Exception as exc:
            log.error(
                "orchestrator.failed",
                phase="rollup",
                error=type(exc).__name__,
                message=str(exc),
            )
            stats.errors.append(
                {"phase": "rollup", "error": f"{type(exc).__name__}: {exc}"}
            )
            finalize_pipeline_run(
                conn,
                run_id,
                status="failed",
                cost_usd_estimate=stats.cost_usd_estimate,
                errors_json=json.dumps(stats.errors),
            )
            conn.commit()
            _write_last_run(stats, status="failed")
            raise


def _rollups_for_render(conn, week_id: str) -> dict[str, object]:
    """Load weekly_rollups rows keyed by scope for the renderer (PIPELINE-05)."""
    return {row["scope"]: row for row in get_rollups_for_week(conn, week_id)}


def _render_status(stats: RunStats, *, budget: WeekBudget | None = None) -> str:
    status = "success" if not stats.errors else "partial"
    if budget is not None and budget.halted:
        status = "partial"
    return status


def _publish_render_outputs(
    conn,
    *,
    week_id: str,
    week_start: datetime,
    week_end: datetime,
    cards: list[DigestCard],
    stats: RunStats,
    run_id: str,
    pending: int,
    failed: int,
    top_n_briefing: int | None,
    partial_publish: bool,
    no_html_preview: bool,
    web_out_dir: Path | None,
    out_dir: Path | None,
    budget: WeekBudget | None = None,
) -> None:
    """Write deprecated HTML preview (optional) and canonical digest JSON (D-A1)."""
    rollups = _rollups_for_render(conn, week_id)
    if not no_html_preview:
        stats.out_path = render_digest(
            week_id=week_id,
            week_start=week_start,
            week_end=week_end,
            cards=cards,
            out_dir=out_dir,
            pipeline_notice_pending_count=pending,
            pipeline_notice_failed_source_count=failed,
            rollups_by_scope=rollups,
            partial_publish=partial_publish,
            top_n_briefing=top_n_briefing,
        )

    status = _render_status(stats, budget=budget)
    pipeline_report = build_pipeline_report(
        conn, stats, run_id=run_id, status=status, budget=budget
    )
    stats.digest_json_path = emit_digest_json(
        week_id=week_id,
        week_start=week_start,
        week_end=week_end,
        cards=cards,
        out_dir=web_out_dir,
        rollups_by_scope=rollups,
        partial_publish=partial_publish,
        top_n_briefing=top_n_briefing,
        pipeline_report=pipeline_report,
        conn=conn,
    )


def run_render(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
    top_n_briefing: int | None = None,
    no_html_preview: bool = False,
    web_out_dir: Path | None = None,
) -> RunStats:
    """Render HTML from existing SQLite data — no network, no LLM (D-20)."""
    init_db(db_path)
    week_start, week_end = week_bounds(week_id)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="render")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="render")
        conn.commit()
        try:
            log.info("orchestrator.start", phase="render")
            week_rows = get_items_for_week(
                conn,
                week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            week_rows = _canonical_rows_for_render(conn, week_rows, week_id=week_id)
            cards = _build_cards_from_db(conn, week_rows, week_id)
            pending, failed = _pipeline_notice_counts(cards=cards, stats=stats)
            _publish_render_outputs(
                conn,
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                cards=cards,
                stats=stats,
                run_id=run_id,
                pending=pending,
                failed=failed,
                top_n_briefing=top_n_briefing,
                partial_publish=False,
                no_html_preview=no_html_preview,
                web_out_dir=web_out_dir,
                out_dir=out_dir,
            )
            _finalize(
                conn, run_id, stats, phase="render", out_dir=out_dir
            )
            return stats
        except Exception as exc:
            log.error(
                "orchestrator.failed",
                phase="render",
                error=type(exc).__name__,
                message=str(exc),
            )
            stats.errors.append(
                {"phase": "render", "error": f"{type(exc).__name__}: {exc}"}
            )
            finalize_pipeline_run(
                conn,
                run_id,
                status="failed",
                errors_json=json.dumps(stats.errors),
            )
            conn.commit()
            _write_last_run(stats, status="failed")
            raise


def run_all(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
    only_pending_transcripts: bool = False,
    max_cost_usd: float | None = None,
    top_n_briefing: int | None = None,
    force_rebuild_clusters: bool = False,
    force_rebuild_rollup: bool = False,
) -> RunStats:
    """Execute ingest → dedup → summarize → categorize → rank → rollup → render."""
    from pipeline.budget import WeekBudget
    from pipeline.config import enabled_sources

    init_db(db_path)
    week_start, week_end = week_bounds(week_id)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="all")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="all")
        conn.commit()

        budget = WeekBudget.from_config(
            cap_override=max_cost_usd, conn=conn, week_id=week_id
        )
        pending_summarize = _count_pending_summarize(
            conn, week_id=week_id, week_start=week_start, week_end=week_end
        )
        budget.set_pre_flight(pending_summarize=pending_summarize)

        try:
            log.info(
                "orchestrator.start",
                phase="all",
                only_pending_transcripts=only_pending_transcripts,
                cap_usd=budget.cap_usd,
            )
            if only_pending_transcripts:
                _ingest_pending_transcripts(
                    conn,
                    log,
                    stats,
                    week_id=week_id,
                    force_rebuild_clusters=force_rebuild_clusters,
                    force_rebuild_rollup=force_rebuild_rollup,
                )
            else:
                sources = enabled_sources()
                if not sources:
                    log.warning("orchestrator.no_sources")

                week_iso = (
                    week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
                _ingest(
                    sources,
                    conn,
                    log,
                    stats,
                    week_id=week_id,
                    week_bounds_iso=week_iso,
                )

            if force_rebuild_clusters:
                delete_clusters_for_week(conn, week_id)
                conn.commit()
            if force_rebuild_rollup:
                delete_rollups_for_week(conn, week_id)
                conn.commit()

            _dedup_week(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                conn=conn,
                log=log,
                stats=stats,
            )
            summaries = _summarize_week_items(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                conn=conn,
                log=log,
                stats=stats,
                budget=budget,
            )
            _categorize_week_clusters(
                week_id=week_id,
                conn=conn,
                log=log,
                stats=stats,
                budget=budget,
            )
            _rank_week(
                week_id=week_id,
                conn=conn,
                log=log,
                stats=stats,
                budget=budget,
            )
            _rollup_week(
                week_id=week_id,
                conn=conn,
                log=log,
                stats=stats,
                budget=budget,
            )

            week_rows = get_items_for_week(
                conn,
                week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            week_rows = _canonical_rows_for_render(conn, week_rows, week_id=week_id)
            cards = _build_cards(
                conn,
                week_id=week_id,
                rows=week_rows,
                summaries=summaries,
            )
            pending, failed = _pipeline_notice_counts(cards=cards, stats=stats)
            _publish_render_outputs(
                conn,
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                cards=cards,
                stats=stats,
                run_id=run_id,
                pending=pending,
                failed=failed,
                top_n_briefing=top_n_briefing,
                partial_publish=budget.halted,
                no_html_preview=False,
                web_out_dir=None,
                out_dir=out_dir,
                budget=budget,
            )

            _finalize(
                conn,
                run_id,
                stats,
                phase="all",
                budget=budget,
                out_dir=out_dir,
            )
            _maybe_write_cron_complete_marker(week_id, log)
            return stats

        except Exception as exc:
            log.error(
                "orchestrator.failed",
                phase="all",
                error=type(exc).__name__,
                message=str(exc),
            )
            stats.errors.append(
                {"phase": "all", "error": f"{type(exc).__name__}: {exc}"}
            )
            finalize_pipeline_run(
                conn,
                run_id,
                status="failed",
                items_fetched=stats.items_fetched,
                summaries_written=stats.summaries_written,
                items_degraded=stats.items_degraded,
                cost_usd_estimate=stats.cost_usd_estimate,
                errors_json=json.dumps(stats.errors),
            )
            conn.commit()
            _write_last_run(stats, status="failed")
            raise


__all__ = [
    "CLOUD_CRON_MODE_ENV",
    "DEFAULT_MARKERS_DIR",
    "RunStats",
    "run_all",
    "run_categorize",
    "run_dedup",
    "run_ingest",
    "run_rank",
    "run_render",
    "run_rollup",
    "run_summarize",
    "write_cron_complete_marker",
]
