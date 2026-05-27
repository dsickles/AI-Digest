"""LOCKED-01 card routing and digest card types.

PROJECT.md **LOCKED** directive (2026-05-22, refined 2026-05-23): the only
items that route to the ``<aside id="also-seen">`` footer are those whose
RSS body is genuinely too short to summarize (``summary_status='thin'``).
Everything else either renders normally or as an in-place degraded card in
the main feed.

Routing table:

1. ``summary_status='ok'`` (or any card with a real ``tldr``) → main feed,
   full card.

2. ``summary_status='thin'`` (RSS body too short to summarize) → footer
   ``<aside id="also-seen">`` as outbound link only. This is the SOLE
   footer category.

3. Everything else (``quota_exhausted``, ``api_error``, ``parse_error``,
   ``client_init_error``, ``transcript_missing``) → main feed, in-place
   degraded card with the locked body copy
   ``"The summary couldn't be generated this week."``

This module is the canonical source of truth for LOCKED-01 routing.
``pipeline/render/html.py`` re-exports these symbols for dev-preview HTML;
``pipeline/render/digest_json.py`` (Plan 04-02) will call the same router.

Import boundary: this module must NOT import adapters or LLM packages —
it only consumes pre-built ``DigestCard`` records (D-20).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

VIDEO_INDICATOR = "[video]"  # D-30: small, unambiguous, structurally minimal
QUOTA_BODY_COPY = "The summary couldn't be generated this week."
ALSO_COVERED_PREFIX = "Also covered by "
ALSO_COVERED_SEPARATOR = ", "

CATEGORY_ORDER = ("edtech", "business", "technical")
CATEGORY_LABELS = {
    "edtech": "Edtech",
    "business": "Business",
    "technical": "Technical",
}
DEFAULT_CATEGORY = "technical"
BRIEFING_HEADER_TEMPLATE = "Briefing — Top {n} this week"
WEEKLY_ROLLUP_FAILURE_COPY = (
    "This week's narrative roll-up couldn't be generated. The Top {n} stories are below."
)
PARTIAL_PUBLISH_COPY = (
    "The pipeline reached its weekly cost cap before finishing every summary. "
    "This digest reflects what completed before the cap."
)

# Summary-status values that warrant an in-place "couldn't be generated" card
# instead of the footer aside. Per LOCKED-01 (2026-05-23 refinement), the ONLY
# status that routes to the footer is 'thin' (RSS body too short to summarize).
#
# Phase 5 plan 05-03 (D-B9) added `deferred_budget` for items the weekly
# $1 hard cap halted before they could be summarized. LOCKED-01 explicitly
# permits new statuses provided they are placed in either the in-place or
# footer bucket — never silently routed by default. See
# `.planning/LOCKED-DIRECTIVES.md` LOCKED-01 amendment 2026-05-27.
_IN_PLACE_TRANSIENT_STATUSES = frozenset(
    {
        "quota_exhausted",
        "api_error",
        "parse_error",
        "client_init_error",
        "transcript_missing",
        "deferred_budget",
    }
)


@dataclass(frozen=True)
class AlsoCoveredMember:
    """Non-canonical cluster member attribution (D-64)."""

    display_name: str
    url: str


@dataclass(frozen=True)
class DigestCard:
    """One card in the digest. Built by the orchestrator from items + summaries.

    ``summary_status`` is the canonical signal that routes a card to the
    main feed vs the footer aside. Healthy cards (status='ok') always go
    in the feed. ``quota_exhausted`` goes in the feed with the
    "couldn't be generated this week" body. Everything else
    (thin / api_error / parse_error / client_init_error / None) routes
    to the footer.
    """

    title: str
    publisher: str
    canonical_url: str
    published_at: datetime
    tldr: str | None
    summary_confidence: str  # 'high' | 'low' | 'unavailable'
    source_type: str = "rss"  # D-30 routes video indicator
    transcript_status: str | None = None  # D-23 lifecycle; informational only
    summary_status: str | None = None  # PROJECT.md LOCKED routing signal
    also_covered: tuple[AlsoCoveredMember, ...] = ()
    category: str | None = None  # cluster category enum for section grouping
    rank_position: int | None = None  # global rank for Briefing + section sort
    channel_url: str | None = None  # Phase 4 UAT: publisher home / channel URL


def _is_quota_in_place(card: DigestCard) -> bool:
    """Quota-exhausted carve-out: card stays in the main feed.

    The check uses ``summary_status`` exclusively. Cards that historically
    have NULL ``summary_status`` but a real ``tldr`` are healthy and go
    in-place via :func:`_is_healthy`; cards with NULL ``summary_status`` and
    no ``tldr`` are treated as thin (footer-bound) by default.
    """
    return card.summary_status in _IN_PLACE_TRANSIENT_STATUSES


def _is_healthy(card: DigestCard) -> bool:
    """A card is healthy when it has a real TL;DR to display."""
    return bool(card.tldr and card.tldr.strip())


def _partition_cards(
    cards: list[DigestCard],
) -> tuple[list[DigestCard], list[DigestCard]]:
    """Return ``(main_feed, also_seen)`` per the PROJECT.md LOCKED-01 directive.

    Main feed:
      * Healthy cards (real ``tldr`` present).
      * In-place degraded cards — ``summary_status`` is one of
        {``quota_exhausted``, ``api_error``, ``parse_error``,
        ``client_init_error``, ``transcript_missing``}. All render with the
        locked "summary couldn't be generated this week" body.

    Also-seen footer (``<aside id="also-seen">``):
      * ``summary_status='thin'`` only — RSS body too short to summarize.
      * Cards with NULL ``summary_status`` AND no ``tldr`` (legacy rows
        where we can't determine the cause) also fall back to footer; the
        orchestrator's ``_infer_summary_status`` should normally prevent
        this case for any modern row.
    """
    main_feed: list[DigestCard] = []
    also_seen: list[DigestCard] = []
    for card in cards:
        if _is_healthy(card) or _is_quota_in_place(card):
            main_feed.append(card)
        else:
            also_seen.append(card)
    return main_feed, also_seen


def _effective_category(card: DigestCard) -> str:
    """Resolve section bucket; uncategorized cards fall back to technical."""
    if card.category in CATEGORY_LABELS:
        return card.category  # type: ignore[return-value]
    return DEFAULT_CATEGORY


def _card_section_sort_key(card: DigestCard) -> tuple[int, float, float]:
    """Rank-ordered within category; unranked cards fall back to recency (D-52)."""
    if card.rank_position is not None:
        return (0, float(card.rank_position), 0.0)
    return (1, 0.0, -card.published_at.timestamp())


def _group_main_feed_by_category(
    main_feed: list[DigestCard],
) -> dict[str, list[DigestCard]]:
    """Bucket main-feed cards by category enum; sort by rank within section."""
    grouped: dict[str, list[DigestCard]] = {key: [] for key in CATEGORY_ORDER}
    for card in main_feed:
        grouped[_effective_category(card)].append(card)
    for key in grouped:
        grouped[key].sort(key=_card_section_sort_key)
    return grouped


__all__ = [
    "ALSO_COVERED_PREFIX",
    "ALSO_COVERED_SEPARATOR",
    "BRIEFING_HEADER_TEMPLATE",
    "CATEGORY_LABELS",
    "CATEGORY_ORDER",
    "DEFAULT_CATEGORY",
    "DigestCard",
    "AlsoCoveredMember",
    "PARTIAL_PUBLISH_COPY",
    "QUOTA_BODY_COPY",
    "VIDEO_INDICATOR",
    "WEEKLY_ROLLUP_FAILURE_COPY",
    "_IN_PLACE_TRANSIENT_STATUSES",
    "_card_section_sort_key",
    "_effective_category",
    "_group_main_feed_by_category",
    "_is_healthy",
    "_is_quota_in_place",
    "_partition_cards",
]
