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
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from pipeline.models import NormalizedItem
from pipeline.render.html import DigestCard, render_digest
from pipeline.reporting.last_run import RunSummary, write_last_run_md
from pipeline.week import week_bounds
from store.db import (
    connect,
    finalize_pipeline_run,
    get_existing_summary,
    get_items_for_week,
    init_db,
    insert_item_summary,
    insert_pipeline_run,
    upsert_item,
    upsert_source,
)

if TYPE_CHECKING:
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
    errors: list[dict[str, str]] = field(default_factory=list)
    out_path: Path | None = None
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


def _ingest(
    sources, conn, log, stats: RunStats
) -> list[NormalizedItem]:
    """Fetch every enabled source; per-source try/except keeps the run alive."""
    from pipeline.adapters.base import FetchError

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
                http_status=None,
                items_count=0,
                error=type(exc).__name__,
                message=str(exc),
            )
            err_msg = f"{type(exc).__name__}: {exc}"
            src_stats.errors.append(err_msg)
            stats.errors.append(
                {
                    "phase": "ingest",
                    "source_id": source.id,
                    "error": err_msg,
                }
            )
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
                message=str(exc),
            )
            err_msg = f"{type(exc).__name__}: {exc}"
            src_stats.errors.append(err_msg)
            stats.errors.append(
                {
                    "phase": "ingest",
                    "source_id": source.id,
                    "error": err_msg,
                }
            )
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

        for item in fetched:
            try:
                upsert_item(conn, item)
            except Exception as exc:
                log.warning(
                    "ingest.upsert.failed",
                    source_id=source.id,
                    title=item.title,
                    error=str(exc),
                )
                stats.errors.append(
                    {
                        "phase": "ingest",
                        "source_id": source.id,
                        "error": f"upsert: {exc}",
                    }
                )
                continue
        all_items.extend(fetched)
    conn.commit()
    stats.items_fetched = len(all_items)
    return all_items


def _summarize_week_items(
    *, week_id: str, week_start: datetime, week_end: datetime, conn, log, stats: RunStats
) -> dict[str, SummaryResult]:
    """Summarize items in [week_start, week_end] missing a current summary."""
    from pipeline.llm.summarize import GeminiKeyMissing, SummaryResult, summarize_item

    rows = get_items_for_week(
        conn,
        week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    summaries: dict[str, SummaryResult] = {}
    for row in rows:
        item_id = row["item_id"]
        existing = get_existing_summary(conn, item_id, week_id, "summarize_v1")
        if existing is not None:
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
            )
            continue

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
        )
        summaries[item_id] = result

        if result.summary_confidence == "unavailable":
            stats.items_degraded += 1
        else:
            stats.summaries_written += 1
        if result.cost_usd_estimate is not None:
            stats.cost_usd_estimate += result.cost_usd_estimate

    conn.commit()
    return summaries


def _build_cards(
    rows, summaries: dict[str, SummaryResult]
) -> list[DigestCard]:
    """Turn item rows + summaries into render-ready cards (newest first)."""
    cards: list[DigestCard] = []
    for row in rows:
        result = summaries.get(row["item_id"])
        cards.append(
            DigestCard(
                title=row["title"],
                publisher=row["publisher"],
                canonical_url=row["canonical_url"],
                published_at=datetime.fromisoformat(
                    row["published_at"].replace("Z", "+00:00")
                ),
                tldr=result.tldr if result else None,
                summary_confidence=result.summary_confidence if result else "unavailable",
            )
        )
    cards.sort(key=lambda c: c.published_at, reverse=True)
    return cards


def _build_cards_from_db(conn, rows, week_id: str) -> list[DigestCard]:
    """Build render cards from SQLite only — no LLM (D-20 render path)."""
    cards: list[DigestCard] = []
    for row in rows:
        existing = get_existing_summary(
            conn, row["item_id"], week_id, "summarize_v1"
        )
        cards.append(
            DigestCard(
                title=row["title"],
                publisher=row["publisher"],
                canonical_url=row["canonical_url"],
                published_at=datetime.fromisoformat(
                    row["published_at"].replace("Z", "+00:00")
                ),
                tldr=existing["tldr"] if existing else None,
                summary_confidence=(
                    existing["summary_confidence"] if existing else "unavailable"
                ),
            )
        )
    cards.sort(key=lambda c: c.published_at, reverse=True)
    return cards


def _write_last_run(stats: RunStats, *, status: str) -> None:
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
) -> None:
    status = "success" if not stats.errors else "partial"
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
    _write_last_run(stats, status=status)
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


def run_ingest(
    week_id: str,
    *,
    db_path: Path | str | None = None,
) -> RunStats:
    """Fetch all enabled sources and upsert into SQLite (no week filter on fetch)."""
    from pipeline.config import enabled_sources

    init_db(db_path)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="ingest")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="ingest")
        conn.commit()
        try:
            log.info("orchestrator.start", phase="ingest")
            sources = enabled_sources()
            if not sources:
                log.warning("orchestrator.no_sources")
            _ingest(sources, conn, log, stats)
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


def run_summarize(
    week_id: str,
    *,
    db_path: Path | str | None = None,
) -> RunStats:
    """Summarize items in the week window that lack a current summary."""
    init_db(db_path)
    week_start, week_end = week_bounds(week_id)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="summarize")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="summarize")
        conn.commit()
        try:
            log.info("orchestrator.start", phase="summarize")
            _summarize_week_items(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                conn=conn,
                log=log,
                stats=stats,
            )
            _finalize(conn, run_id, stats, phase="summarize")
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


def run_render(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
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
            cards = _build_cards_from_db(conn, week_rows, week_id)
            stats.out_path = render_digest(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                cards=cards,
                out_dir=out_dir,
            )
            _finalize(conn, run_id, stats, phase="render")
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
) -> RunStats:
    """Execute ingest → summarize → render for ``week_id``."""
    from pipeline.config import enabled_sources

    init_db(db_path)
    week_start, week_end = week_bounds(week_id)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="all")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="all")
        conn.commit()

        try:
            log.info("orchestrator.start", phase="all")
            sources = enabled_sources()
            if not sources:
                log.warning("orchestrator.no_sources")

            _ingest(sources, conn, log, stats)
            summaries = _summarize_week_items(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                conn=conn,
                log=log,
                stats=stats,
            )

            week_rows = get_items_for_week(
                conn,
                week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            cards = _build_cards(week_rows, summaries)
            stats.out_path = render_digest(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                cards=cards,
                out_dir=out_dir,
            )

            _finalize(conn, run_id, stats, phase="all")
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
    "RunStats",
    "run_all",
    "run_ingest",
    "run_render",
    "run_summarize",
]
