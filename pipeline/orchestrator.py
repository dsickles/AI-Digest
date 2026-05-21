"""End-to-end orchestrator — wires ingest → store → summarize → render.

Single function ``run_all`` for the skeleton; Plan 01-04 splits this
into ``ingest`` / ``summarize`` / ``render`` / ``all`` subcommands.

Per-source try/except gives us PROJECT.md per-source isolation
(one bad feed cannot break the weekly run) even though the formal
INGEST-06 requirement lands in Phase 2.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import structlog

from pipeline.adapters.base import FetchError
from pipeline.adapters.rss import RssAdapter
from pipeline.config import enabled_sources
from pipeline.llm.summarize import (
    GeminiKeyMissing,
    SummaryResult,
    summarize_item,
)
from pipeline.models import NormalizedItem
from pipeline.render.html import DigestCard, render_digest
from pipeline.week import current_week_id, week_bounds
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

logger = structlog.get_logger(__name__)


@dataclass
class RunStats:
    week_id: str
    items_fetched: int = 0
    summaries_written: int = 0
    items_degraded: int = 0
    cost_usd_estimate: float = 0.0
    errors: list[dict[str, str]] = None  # type: ignore[assignment]
    out_path: Path | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def _pick_adapter(source_type: str):
    """One-line registry. Phase 2 grows this dict."""
    if source_type == "rss":
        return RssAdapter()
    raise ValueError(f"no adapter registered for source type {source_type!r}")


def _ingest(
    sources, conn, log, stats: RunStats
) -> list[NormalizedItem]:
    """Fetch every enabled source; per-source try/except keeps the run alive."""
    all_items: list[NormalizedItem] = []
    for source in sources:
        upsert_source(conn, source)
        try:
            adapter = _pick_adapter(source.type)
            fetched = adapter.fetch(source)
        except FetchError as exc:
            log.error(
                "ingest.source.failed",
                source_id=source.id,
                error=type(exc).__name__,
                message=str(exc),
            )
            stats.errors.append(
                {
                    "phase": "ingest",
                    "source_id": source.id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        except Exception as exc:
            log.error(
                "ingest.source.failed",
                source_id=source.id,
                error=type(exc).__name__,
                message=str(exc),
            )
            stats.errors.append(
                {
                    "phase": "ingest",
                    "source_id": source.id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

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
        log.info(
            "ingest.source.complete",
            source_id=source.id,
            items=len(fetched),
        )
    conn.commit()
    stats.items_fetched = len(all_items)
    return all_items


def _summarize_week_items(
    *, week_id: str, week_start: datetime, week_end: datetime, conn, log, stats: RunStats
) -> dict[str, SummaryResult]:
    """Summarize items in [week_start, week_end) that have no prior summary for this prompt."""
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
            )
            continue

        try:
            result = summarize_item(
                title=row["title"],
                publisher=row["publisher"],
                raw_content=row["raw_content"] or "",
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
    return cards


def run_all(
    week_id: str | None = None,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
) -> RunStats:
    """Execute the full pipeline for ``week_id`` (defaults to current ISO week UTC).

    Returns a ``RunStats`` summary for the CLI / observability layer.
    """
    init_db(db_path)
    resolved_week = week_id or current_week_id()
    week_start, week_end = week_bounds(resolved_week)
    log = logger.bind(week_id=resolved_week)
    stats = RunStats(week_id=resolved_week)

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=resolved_week, phase="all")
        conn.commit()

        try:
            log.info("orchestrator.start", phase="all")
            sources = enabled_sources()
            if not sources:
                log.warning("orchestrator.no_sources")

            _ingest(sources, conn, log, stats)
            summaries = _summarize_week_items(
                week_id=resolved_week,
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
                week_id=resolved_week,
                week_start=week_start,
                week_end=week_end,
                cards=cards,
                out_dir=out_dir,
            )

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
            log.info(
                "orchestrator.complete",
                status=status,
                items_fetched=stats.items_fetched,
                summaries_written=stats.summaries_written,
                items_degraded=stats.items_degraded,
                cost_usd_estimate=round(stats.cost_usd_estimate, 6),
                out_path=str(stats.out_path),
            )
            return stats

        except Exception as exc:
            log.error(
                "orchestrator.failed",
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
            raise


__all__ = ["RunStats", "run_all"]
