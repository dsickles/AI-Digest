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
from pipeline.render.html import AlsoCoveredMember, DigestCard, render_digest
from pipeline.reporting.last_run import RunSummary, write_last_run_md
from pipeline.week import week_bounds
from store.db import (
    connect,
    finalize_pipeline_run,
    get_canonical_item_ids_for_week,
    get_cluster_categories_for_week,
    get_cluster_members,
    get_clusters_for_week,
    get_existing_cluster_summary,
    get_existing_summary,
    get_items_for_week,
    get_last_known_cluster_category,
    get_pending_transcript_items,
    get_rank_positions_for_week,
    get_ranks_for_week,
    init_db,
    insert_cluster_ranks_batch,
    insert_cluster_summary,
    insert_item_summary,
    insert_pipeline_run,
    update_item_transcript,
    update_source_health,
    upsert_item,
    upsert_source,
)


def _utc_iso_now() -> str:
    """Second-precision ISO 8601 UTC timestamp (matches items.published_at format)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

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
    clusters_created: int = 0
    items_clustered: int = 0
    categorize_llm_calls: int = 0
    rank_llm_calls: int = 0
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
    sources, conn, log, stats: RunStats, *, week_bounds_iso: tuple[str, str] | None = None
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
            try:
                upsert_item(conn, item)
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
    *, week_id: str, week_start: datetime, week_end: datetime, conn, log, stats: RunStats
) -> dict[str, SummaryResult]:
    """Summarize items in [week_start, week_end] missing a current summary."""
    from pipeline.llm.summarize import GeminiKeyMissing, SummaryResult, summarize_item

    rows = get_items_for_week(
        conn,
        week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    canonical_ids = get_canonical_item_ids_for_week(conn, week_id)
    if not canonical_ids:
        canonical_ids = {row["item_id"] for row in rows}

    summaries: dict[str, SummaryResult] = {}
    for row in rows:
        item_id = row["item_id"]
        if item_id not in canonical_ids:
            continue
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
            summary_status=result.summary_status,
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
    *, week_id: str, conn, log, stats: RunStats
) -> None:
    """Item-level categorize checkpoint — skip rows already persisted (D-67)."""
    from pipeline.llm.categorize import PROMPT_VERSION, categorize_cluster
    from pipeline.llm.summarize import GeminiKeyMissing

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


def _rank_week(*, week_id: str, conn, log, stats: RunStats) -> None:
    """Stage-level rank checkpoint — single LLM call per week (D-67)."""
    from pipeline.llm.rank import PROMPT_VERSION, rank_week_clusters
    from pipeline.llm.summarize import GeminiKeyMissing

    existing = get_ranks_for_week(conn, week_id, PROMPT_VERSION)
    if existing:
        log.info("rank.skip_existing", count=len(existing))
        return

    cluster_inputs = _load_cluster_rank_inputs(conn, week_id)
    if not cluster_inputs:
        log.info("rank.no_clusters")
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
    a conservative status so the renderer can still route them correctly:

    * tldr present                                  → ``ok``
    * transcript_status in {pending_local, missing} → ``thin`` (footer)
    * summary_confidence == 'unavailable'           → ``thin`` (footer)
    * fallback                                      → ``thin``

    Default to footer-bound when in doubt; the PROJECT.md LOCKED rule says
    only the explicit ``quota_exhausted`` carve-out earns an in-place slot.
    """
    if persisted_status:
        return persisted_status
    if tldr and tldr.strip():
        return "ok"
    if transcript_status in {"pending_local", "missing"}:
        return "thin"
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
            clusters_created=stats.clusters_created,
            items_clustered=stats.items_clustered,
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


def _ingest_pending_transcripts(conn, log, stats: RunStats) -> int:
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
        if raw_content is not None:
            update_item_transcript(
                conn,
                row["item_id"],
                transcript_status=new_status,
                raw_content=raw_content,
            )
            conn.execute(
                "UPDATE items SET content_hash = ? WHERE item_id = ?",
                (hash_content(raw_content), row["item_id"]),
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
                _ingest_pending_transcripts(conn, log, stats)
                _finalize(conn, run_id, stats, phase="ingest")
                return stats
            sources = enabled_sources()
            if not sources:
                log.warning("orchestrator.no_sources")
            _ingest(sources, conn, log, stats, week_bounds_iso=week_iso)
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
            _dedup_week(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                conn=conn,
                log=log,
                stats=stats,
            )
            _finalize(conn, run_id, stats, phase="dedup")
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


def run_categorize(
    week_id: str,
    *,
    db_path: Path | str | None = None,
) -> RunStats:
    """Classify story clusters into edtech|business|technical|design."""
    init_db(db_path)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="categorize")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="categorize")
        conn.commit()
        try:
            log.info("orchestrator.start", phase="categorize")
            _categorize_week_clusters(
                week_id=week_id,
                conn=conn,
                log=log,
                stats=stats,
            )
            _finalize(conn, run_id, stats, phase="categorize")
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
) -> RunStats:
    """Rank story clusters for the week (single LLM call)."""
    init_db(db_path)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="rank")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="rank")
        conn.commit()
        try:
            log.info("orchestrator.start", phase="rank")
            _rank_week(week_id=week_id, conn=conn, log=log, stats=stats)
            _finalize(conn, run_id, stats, phase="rank")
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
            week_rows = _canonical_rows_for_render(conn, week_rows, week_id=week_id)
            cards = _build_cards_from_db(conn, week_rows, week_id)
            pending, failed = _pipeline_notice_counts(cards=cards, stats=stats)
            stats.out_path = render_digest(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                cards=cards,
                out_dir=out_dir,
                pipeline_notice_pending_count=pending,
                pipeline_notice_failed_source_count=failed,
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
    only_pending_transcripts: bool = False,
) -> RunStats:
    """Execute ingest → dedup → summarize → categorize → rank → render for ``week_id``."""
    from pipeline.config import enabled_sources

    init_db(db_path)
    week_start, week_end = week_bounds(week_id)
    log = logger.bind(week_id=week_id)
    stats = RunStats(week_id=week_id, phase="all")

    with connect(db_path) as conn:
        run_id = insert_pipeline_run(conn, week_id=week_id, phase="all")
        conn.commit()

        try:
            log.info(
                "orchestrator.start",
                phase="all",
                only_pending_transcripts=only_pending_transcripts,
            )
            if only_pending_transcripts:
                _ingest_pending_transcripts(conn, log, stats)
            else:
                sources = enabled_sources()
                if not sources:
                    log.warning("orchestrator.no_sources")

                week_iso = (
                    week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
                _ingest(sources, conn, log, stats, week_bounds_iso=week_iso)
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
            )
            _categorize_week_clusters(
                week_id=week_id,
                conn=conn,
                log=log,
                stats=stats,
            )
            _rank_week(
                week_id=week_id,
                conn=conn,
                log=log,
                stats=stats,
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
            stats.out_path = render_digest(
                week_id=week_id,
                week_start=week_start,
                week_end=week_end,
                cards=cards,
                out_dir=out_dir,
                pipeline_notice_pending_count=pending,
                pipeline_notice_failed_source_count=failed,
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
    "run_categorize",
    "run_dedup",
    "run_ingest",
    "run_rank",
    "run_render",
    "run_summarize",
]
