"""Pre-partitioned digest JSON emitter for Astro archive (D-A1, ARCHIVE-01).

LOCKED-01 routing runs through ``partition._partition_cards`` — Astro receives
pre-routed ``main_feed``, ``footer_aside``, and ``briefing_top_n`` lists only.

Import boundary: no adapter or LLM packages (D-20).
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

from pipeline.render.partition import (
    CATEGORY_ORDER,
    PARTIAL_PUBLISH_COPY,
    QUOTA_BODY_COPY,
    DigestCard,
    _group_main_feed_by_category,
    _is_healthy,
    _is_quota_in_place,
    _partition_cards,
)
from pipeline.week import prior_week_id, week_bounds

logger = structlog.get_logger(__name__)

DEFAULT_WEB_CONTENT_DIR = Path("web/src/content/digests")

_FETCH_FAILURE_CATEGORIES = frozenset(
    {
        "fetch_timeout",
        "fetch_http_error",
        "parse_error",
        "adapter_internal",
    }
)

_ORDINAL_WORDS = {
    1: "first",
    2: "second",
    3: "third",
    4: "fourth",
    5: "fifth",
}


class AlsoCoveredJson(BaseModel):
    display_name: str
    url: str


class DigestCardJson(BaseModel):
    title: str
    publisher: str
    canonical_url: str
    published_at: str
    tldr: str | None
    summary_status: str | None
    source_type: str = "rss"
    also_covered: list[AlsoCoveredJson] = Field(default_factory=list)
    category: str | None = None
    rank_position: int | None = None
    degraded_body: str | None = None
    channel_url: str | None = None


class WeekRangeJson(BaseModel):
    start: str
    end: str


class WeeklySynthesisJson(BaseModel):
    text: str | None = None
    status: str


class CategorySectionJson(BaseModel):
    mini_rollup: str | None = None
    cards: list[DigestCardJson] = Field(default_factory=list)


class CategorySectionsJson(BaseModel):
    edtech: CategorySectionJson
    business: CategorySectionJson
    technical: CategorySectionJson


class PipelineNotesJson(BaseModel):
    show: bool = True
    summary_line: str
    details: list[str] = Field(default_factory=list)


class FailureNoticeJson(BaseModel):
    kind: str
    body: str


class DigestDocument(BaseModel):
    schema_version: Literal[1] = 1
    week_id: str
    generated_at: str
    week_range: WeekRangeJson
    updated_at: str
    weekly_synthesis: WeeklySynthesisJson
    briefing_top_n: list[DigestCardJson]
    category_sections: CategorySectionsJson
    main_feed: list[DigestCardJson]
    footer_aside: list[DigestCardJson]
    pipeline_notes: PipelineNotesJson | None = None
    failure_notice: FailureNoticeJson | None = None


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_iso_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rollup_row_value(row: object | None, key: str) -> object | None:
    if row is None:
        return None
    if hasattr(row, "keys") and key in row.keys():  # type: ignore[union-attr]
        return row[key]  # type: ignore[index]
    return getattr(row, key, None)


def _rollup_status_ok(row: object | None) -> bool:
    if row is None:
        return False
    status = _rollup_row_value(row, "rollup_status")
    narrative = _rollup_row_value(row, "narrative_md")
    return status == "ok" and bool(narrative and str(narrative).strip())


def _card_to_json(card: DigestCard) -> DigestCardJson:
    degraded: str | None = None
    if _is_quota_in_place(card) and not _is_healthy(card):
        degraded = QUOTA_BODY_COPY
    return DigestCardJson(
        title=card.title,
        publisher=card.publisher,
        canonical_url=card.canonical_url,
        published_at=_utc_iso(card.published_at),
        tldr=card.tldr,
        summary_status=card.summary_status,
        source_type=card.source_type,
        also_covered=[
            AlsoCoveredJson(display_name=member.display_name, url=member.url)
            for member in card.also_covered
        ],
        category=card.category,
        rank_position=card.rank_position,
        degraded_body=degraded,
        channel_url=card.channel_url,
    )


def _select_briefing_top_n(main_feed: list[DigestCard], *, top_n: int) -> list[DigestCard]:
    ranked = [card for card in main_feed if card.rank_position is not None]
    ranked.sort(key=lambda c: c.rank_position)  # type: ignore[arg-type, return-value]
    return ranked[:top_n]


def _weekly_synthesis_from_rollups(
    rollups_by_scope: dict[str, object],
) -> WeeklySynthesisJson:
    weekly_row = rollups_by_scope.get("weekly")
    if _rollup_status_ok(weekly_row):
        return WeeklySynthesisJson(
            text=str(_rollup_row_value(weekly_row, "narrative_md")),
            status="ok",
        )
    status = _rollup_row_value(weekly_row, "rollup_status")
    return WeeklySynthesisJson(text=None, status=str(status) if status else "missing")


def _category_sections_from_rollups(
    grouped: dict[str, list[DigestCard]],
    rollups_by_scope: dict[str, object],
) -> CategorySectionsJson:
    sections: dict[str, CategorySectionJson] = {}
    for category in CATEGORY_ORDER:
        scope = f"category:{category}"
        row = rollups_by_scope.get(scope)
        mini: str | None = None
        if _rollup_status_ok(row):
            mini = str(_rollup_row_value(row, "narrative_md"))
        cards = grouped.get(category, [])
        sections[category] = CategorySectionJson(
            mini_rollup=mini,
            cards=[_card_to_json(card) for card in cards],
        )
    return CategorySectionsJson(
        edtech=sections["edtech"],
        business=sections["business"],
        technical=sections["technical"],
    )


def _publisher_display_name(source_id: str) -> str:
    from pipeline.config import load_sources

    for source in load_sources():
        if source.id == source_id:
            return source.display_name
    return source_id


def _consecutive_empty_weeks(conn, source_id: str, week_id: str) -> int:
    """Count consecutive ISO weeks (including current) with zero in-window items."""
    count = 0
    current = week_id
    for _ in range(12):
        start, end = week_bounds(current)
        start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end.strftime("%Y-%m-%dT%H:%M:%SZ")
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
              FROM items
             WHERE source_id = ?
               AND published_at >= ?
               AND published_at <= ?
            """,
            (source_id, start_iso, end_iso),
        ).fetchone()
        items_n = int(row["n"]) if row else 0
        if items_n > 0:
            break
        count += 1
        try:
            current = prior_week_id(current)
        except ValueError:
            break
    return count


def _silent_source_detail(conn, source_id: str, week_id: str) -> str | None:
    streak = _consecutive_empty_weeks(conn, source_id, week_id)
    if streak < 3:
        return None
    publisher = _publisher_display_name(source_id)
    if streak in _ORDINAL_WORDS:
        ordinal = _ORDINAL_WORDS[streak]
        return f"{publisher} didn't publish for the {ordinal} week in a row."
    return f"{publisher} didn't publish for the {streak}th week in a row."


def _build_pipeline_notes(
    *,
    cards: list[DigestCard],
    pipeline_report: dict[str, Any] | None,
    conn,
    week_id: str,
) -> PipelineNotesJson | None:
    details: list[str] = []
    pending_local = sum(1 for c in cards if c.transcript_status == "pending_local")

    report = pipeline_report or {}
    summary_status = report.get("summary_status") or {}
    budget = report.get("budget") or {}
    source_health = report.get("source_health") or {}

    quota_n = int(summary_status.get("quota_exhausted", 0))
    if quota_n > 0:
        noun = "summary" if quota_n == 1 else "summaries"
        details.append(
            f"{quota_n} {noun} hit the weekly LLM budget and weren't generated this run."
        )

    for status in ("api_error", "parse_error", "client_init_error"):
        n = int(summary_status.get(status, 0))
        if n <= 0:
            continue
        noun = "summary" if n == 1 else "summaries"
        details.append(
            f"{n} {noun} couldn't be generated this run due to a processing error."
        )

    deferred_n = int(summary_status.get("deferred_budget", 0))
    if deferred_n > 0:
        # D-24: plain English on reader surface — never expose the
        # `deferred_budget` sentinel itself. The number is enough.
        noun = "story" if deferred_n == 1 else "stories"
        details.append(
            f"{deferred_n} {noun} were skipped after the weekly spend cap was reached."
        )

    for source_id, health in source_health.items():
        err = health.get("last_error_category")
        if err in _FETCH_FAILURE_CATEGORIES:
            publisher = _publisher_display_name(source_id)
            details.append(
                f"{publisher} couldn't be reached this Sunday morning. "
                "The next run will retry."
            )
        elif conn is not None and (
            err == "empty_feed"
            or (health.get("items_this_week", 0) == 0 and not err)
        ):
            silent = _silent_source_detail(conn, source_id, week_id)
            if silent:
                details.append(silent)

    if pending_local > 0:
        noun = "transcript" if pending_local == 1 else "transcripts"
        details.append(
            f"{pending_local} video {noun} will fill in when the digest is "
            "refreshed from a different network."
        )

    if budget.get("halted"):
        details.append(PARTIAL_PUBLISH_COPY)

    if not details:
        return None

    summary_parts: list[str] = []
    if pending_local > 0:
        verb = "summary" if pending_local == 1 else "summaries"
        summary_parts.append(
            f"{pending_local} video {verb} pending"
        )
    fetch_failures = sum(
        1
        for health in source_health.values()
        if health.get("last_error_category") in _FETCH_FAILURE_CATEGORIES
    )
    if fetch_failures > 0:
        noun = "source" if fetch_failures == 1 else "sources"
        summary_parts.append(f"{fetch_failures} {noun} unreachable")
    if quota_n > 0:
        summary_parts.append(f"{quota_n} budget-limited summaries")
    if budget.get("halted"):
        summary_parts.append("pipeline stopped at budget cap")

    summary_line = "; ".join(summary_parts) if summary_parts else details[0]
    return PipelineNotesJson(show=True, summary_line=summary_line, details=details)


def emit_digest_json(
    *,
    week_id: str,
    week_start: datetime,
    week_end: datetime,
    cards: list[DigestCard],
    out_dir: Path | None = None,
    rollups_by_scope: dict[str, object] | None = None,
    partial_publish: bool = False,
    top_n_briefing: int | None = None,
    pipeline_report: dict[str, Any] | None = None,
    conn=None,
) -> Path:
    """Write pre-partitioned digest JSON and return the output path."""
    out_root = out_dir or DEFAULT_WEB_CONTENT_DIR
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"{week_id}.json"

    from pipeline.config import load_digest_config

    top_n = top_n_briefing
    if top_n is None:
        top_n = load_digest_config().top_n_briefing

    rollups = rollups_by_scope or {}
    main_feed, footer_aside = _partition_cards(cards)
    grouped = _group_main_feed_by_category(main_feed)
    briefing_cards = _select_briefing_top_n(main_feed, top_n=top_n)

    footer_sorted = sorted(footer_aside, key=lambda c: c.published_at, reverse=True)

    pipeline_notes = _build_pipeline_notes(
        cards=cards,
        pipeline_report=pipeline_report,
        conn=conn,
        week_id=week_id,
    )

    failure_notice: FailureNoticeJson | None = None
    if partial_publish:
        failure_notice = FailureNoticeJson(
            kind="partial_publish",
            body=PARTIAL_PUBLISH_COPY,
        )

    now_iso = _utc_iso_now()
    doc = DigestDocument(
        week_id=week_id,
        generated_at=now_iso,
        week_range=WeekRangeJson(
            start=_utc_iso(week_start),
            end=_utc_iso(week_end),
        ),
        updated_at=now_iso,
        weekly_synthesis=_weekly_synthesis_from_rollups(rollups),
        briefing_top_n=[_card_to_json(card) for card in briefing_cards],
        category_sections=_category_sections_from_rollups(grouped, rollups),
        main_feed=[_card_to_json(card) for card in main_feed],
        footer_aside=[_card_to_json(card) for card in footer_sorted],
        pipeline_notes=pipeline_notes,
        failure_notice=failure_notice,
    )

    out_path.write_text(doc.model_dump_json(indent=2) + "\n", encoding="utf-8")
    logger.info(
        "digest_json.written",
        week_id=week_id,
        path=str(out_path),
        main_feed_count=len(main_feed),
        footer_aside_count=len(footer_aside),
    )
    return out_path


__all__ = [
    "CategorySectionJson",
    "CategorySectionsJson",
    "DigestCardJson",
    "DigestDocument",
    "FailureNoticeJson",
    "PipelineNotesJson",
    "WeekRangeJson",
    "WeeklySynthesisJson",
    "emit_digest_json",
]
