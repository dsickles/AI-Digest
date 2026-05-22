"""Plain-HTML weekly digest renderer.

PROJECT.md **LOCKED** directive (2026-05-22): items the pipeline could not
turn into a real TL;DR fall into two buckets:

1. **Content-thin / unsummarizable** — RSS body too short, YouTube transcript
   missing/pending, content_too_thin gate, enrichment failure, parse error,
   etc. These go to the ``<aside id="also-seen">`` footer as outbound links
   only. They do **not** appear in the main feed. This is non-negotiable.

2. **Transient LLM-call failure** — the only carve-out. When the summary
   could not be generated because the LLM call itself failed for a
   transient reason (rate-limit / quota exhausted / ``RESOURCE_EXHAUSTED``
   / HTTP 429), the item DOES appear in the main feed as an in-place card
   with "summary couldn't be generated this week" body copy. These items
   had enough content to summarize and the next run is likely to succeed.

This rule supersedes Phase 1 D-05 (footer-link style) and Phase 2 D-25
(in-place degradation). Plan 01-03 inline-regressed on it once (reverted
5f8e9f0) and Plan 02-03 attempted to override it; this module is now the
single source of truth and must not be loosened by phase-level plans.

D-26 adds a top-of-digest ``<p class="pipeline-notice">`` element placed
directly under the ``Updated …`` timestamp. It is rendered only when there
is something to surface (pending-local transcripts or failed sources);
otherwise the element is omitted entirely. Reader-facing copy follows
D-24 plain-English language policy — no CLI flag syntax, no file paths,
no error class names.

D-30 adds a small ``[video]`` indicator to the publisher badge on YouTube
cards. Phase 4 DISPLAY-06 owns the formal glyph polish.

Import boundary: this module must NOT import adapters or LLM packages —
it only consumes pre-built ``DigestCard`` records (D-20).
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_OUT_DIR = Path("out")
VIDEO_INDICATOR = "[video]"  # D-30: small, unambiguous, structurally minimal
QUOTA_BODY_COPY = "The summary couldn't be generated this week."

# Summary-status values that warrant an in-place "couldn't be generated" card
# instead of the footer aside. ``parse_error`` and ``api_error`` are bundled
# with ``quota_exhausted`` because they all share the same UX shape: the
# content was summarizable but the LLM round-trip failed transiently.
_IN_PLACE_TRANSIENT_STATUSES = frozenset({"quota_exhausted"})


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


_CSS = """
:root { color-scheme: dark; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #0e1116;
  color: #e6e6e6;
  line-height: 1.6;
}
header {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1.25rem 1rem;
  border-bottom: 1px solid #2a3140;
}
header h1 { margin: 0 0 0.35rem; font-size: 1.75rem; font-weight: 650; }
header .week-range { margin: 0; color: #9aa3b2; font-size: 1rem; }
header .updated { margin: 0.35rem 0 0; color: #6b7280; font-size: 0.85rem; }
header .pipeline-notice {
  margin: 0.6rem 0 0;
  padding: 0.55rem 0.8rem;
  border-left: 3px solid #4a5260;
  background: #141820;
  color: #9aa3b2;
  font-size: 0.88rem;
  border-radius: 3px;
}
main {
  max-width: 720px;
  margin: 0 auto;
  padding: 1.25rem;
}
.card {
  border: 1px solid #2a3140;
  border-radius: 8px;
  padding: 1.1rem 1.25rem;
  margin-bottom: 1rem;
  background: #141820;
}
.card-meta {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  font-size: 0.82rem;
  color: #9aa3b2;
  margin-bottom: 0.4rem;
}
.source-badge {
  background: #1f2630;
  color: #c8cdd5;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  font-size: 0.78rem;
}
.video-indicator {
  margin-left: 0.35rem;
  color: #9aa3b2;
  font-size: 0.72rem;
  letter-spacing: 0.04em;
}
.card-title { margin: 0 0 0.55rem; font-size: 1.1rem; line-height: 1.35; }
.card-title a { color: #e6e6e6; text-decoration: none; }
.card-title a:hover { color: #7eb6ff; text-decoration: underline; }
.card-tldr { margin: 0; color: #c8cdd5; }
.card-degraded { margin: 0; color: #9aa3b2; font-style: italic; }
#also-seen {
  max-width: 720px;
  margin: 0 auto 2rem;
  padding: 1rem 1.25rem 1.5rem;
  border-top: 1px solid #2a3140;
  color: #9aa3b2;
}
#also-seen h2 {
  margin: 0 0 0.6rem;
  font-size: 1rem;
  font-weight: 600;
  color: #c8cdd5;
}
#also-seen ul {
  margin: 0;
  padding: 0 0 0 1.1rem;
  font-size: 0.9rem;
}
#also-seen li { margin-bottom: 0.35rem; }
#also-seen a { color: #c8cdd5; text-decoration: none; }
#also-seen a:hover { color: #7eb6ff; text-decoration: underline; }
#also-seen .also-meta {
  margin-left: 0.4rem;
  font-size: 0.78rem;
  color: #6b7280;
}
""".strip()


def _day_label(dt: datetime) -> str:
    """``May 4`` style day without platform-specific ``%-d``."""
    local = dt.astimezone(UTC)
    return f"{local.strftime('%b')} {local.day}"


def _format_week_header(week_start: datetime, week_end: datetime) -> str:
    """D-18: ``Week of May 4 – May 10, 2026``."""
    return f"Week of {_day_label(week_start)} – {_day_label(week_end)}, {week_end.year}"


def _format_updated(now: datetime) -> str:
    iso = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"Updated {iso}"


def _format_date(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d")


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
    """Return ``(main_feed, also_seen)`` per the PROJECT.md LOCKED directive.

    Main feed:
      * Healthy cards (tldr present).
      * Quota-exhausted cards (LLM call failed transiently, content was fine).

    Also-seen footer:
      * Everything else — content too thin, transcript missing/pending,
        parse error, api error, client init error, or a card with neither
        a tldr nor a recognised transient ``summary_status``.
    """
    main_feed: list[DigestCard] = []
    also_seen: list[DigestCard] = []
    for card in cards:
        if _is_healthy(card) or _is_quota_in_place(card):
            main_feed.append(card)
        else:
            also_seen.append(card)
    return main_feed, also_seen


def _render_body(card: DigestCard) -> str:
    """Main-feed body copy. ``quote=False`` keeps apostrophes readable in
    text content while ``<``, ``>``, ``&`` still escape, mitigating
    T-02-01 (untrusted strings reaching the browser)."""
    if _is_healthy(card):
        return f'<p class="card-tldr">{html.escape(card.tldr or "", quote=False)}</p>'
    return f'<p class="card-degraded">{html.escape(QUOTA_BODY_COPY, quote=False)}</p>'


def _render_card(card: DigestCard) -> str:
    title_safe = html.escape(card.title)
    badge_safe = html.escape(f"[{card.publisher}]")
    url_safe = html.escape(card.canonical_url, quote=True)
    date_safe = html.escape(_format_date(card.published_at))

    if card.source_type == "youtube":
        video_suffix = f'<span class="video-indicator">{html.escape(VIDEO_INDICATOR)}</span>'
    else:
        video_suffix = ""

    return (
        '<article class="card">'
        '<div class="card-meta">'
        f'<span class="source-badge">{badge_safe}</span>{video_suffix}'
        f"<span>{date_safe}</span>"
        "</div>"
        '<h2 class="card-title">'
        f'<a href="{url_safe}" target="_blank" rel="noopener">{title_safe}</a>'
        "</h2>"
        f"{_render_body(card)}"
        "</article>"
    )


def _render_also_seen(also_seen: list[DigestCard]) -> str:
    """Footer aside: outbound link + publisher + date per item, no body.

    Sorted newest-first to mirror the main feed. Hidden entirely when the
    list is empty.
    """
    if not also_seen:
        return ""
    items: list[str] = []
    for card in sorted(also_seen, key=lambda c: c.published_at, reverse=True):
        title_safe = html.escape(card.title)
        url_safe = html.escape(card.canonical_url, quote=True)
        publisher_safe = html.escape(f"[{card.publisher}]")
        date_safe = html.escape(_format_date(card.published_at))
        items.append(
            f'<li><a href="{url_safe}" target="_blank" rel="noopener">{title_safe}</a>'
            f'<span class="also-meta">{publisher_safe} · {date_safe}</span></li>'
        )
    return (
        '<aside id="also-seen">'
        "<h2>Also seen this week</h2>"
        "<ul>" + "".join(items) + "</ul>"
        "</aside>"
    )


def _render_pipeline_notice(*, pending: int, failed_sources: int) -> str:
    """D-26 header pipeline-notice. Returns empty string at zero state.

    Copy is plain-English per D-24 — no CLI flag syntax, no error class names.
    Two independent clauses; either may appear alone.
    """
    if pending <= 0 and failed_sources <= 0:
        return ""

    clauses: list[str] = []
    if pending > 0:
        verb = "summary" if pending == 1 else "summaries"
        clauses.append(
            f"{pending} video {verb} will fill in once captions can be reached "
            "from a different network."
        )
    if failed_sources > 0:
        noun = "source" if failed_sources == 1 else "sources"
        clauses.append(
            f"{failed_sources} {noun} couldn't be reached this week; "
            "the missing items should reappear next run."
        )

    body = " ".join(html.escape(c) for c in clauses)
    return f'<p class="pipeline-notice">{body}</p>'


def render_digest(
    *,
    week_id: str,
    week_start: datetime,
    week_end: datetime,
    cards: list[DigestCard],
    out_dir: Path | None = None,
    pipeline_notice_pending_count: int = 0,
    pipeline_notice_failed_source_count: int = 0,
) -> Path:
    """Write the weekly digest HTML and return the output path.

    Per the PROJECT.md LOCKED directive, cards are partitioned into the main
    feed (healthy + quota-exhausted) and the ``<aside id="also-seen">``
    footer (everything else). The header item count reflects the main-feed
    size only — items in the footer aside are referenced but not counted
    against the week's "real" item total.
    """
    out_root = out_dir or DEFAULT_OUT_DIR
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"digest-{week_id}.html"

    main_feed, also_seen = _partition_cards(cards)
    main_sorted = sorted(main_feed, key=lambda c: c.published_at, reverse=True)

    week_header = _format_week_header(week_start, week_end)
    updated_line = _format_updated(datetime.now(UTC))
    notice_html = _render_pipeline_notice(
        pending=pipeline_notice_pending_count,
        failed_sources=pipeline_notice_failed_source_count,
    )

    week_header_safe = html.escape(week_header)
    updated_safe = html.escape(updated_line)

    if main_sorted:
        cards_html = "\n".join(_render_card(card) for card in main_sorted)
    else:
        cards_html = (
            '<p class="card-degraded">'
            "No items have full summaries this week. See \u201cAlso seen this week\u201d "
            "below for outbound links."
            "</p>"
        )

    also_seen_html = _render_also_seen(also_seen)

    total_main = len(main_sorted)
    item_word = "item" if total_main == 1 else "items"
    also_seen_suffix = (
        f" · {len(also_seen)} more in footer" if also_seen else ""
    )
    header_count_line = f"{total_main} {item_word}{also_seen_suffix}"

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Digest — {html.escape(week_id)}</title>
<style>
{_CSS}
</style>
</head>
<body>
<header>
  <h1>AI Digest</h1>
  <p class="week-range">{week_header_safe} · {header_count_line}</p>
  <p class="updated">{updated_safe}</p>
{notice_html}
</header>
<main>
{cards_html}
</main>
{also_seen_html}
</body>
</html>
"""

    out_path.write_text(document, encoding="utf-8")
    logger.info(
        "render_complete",
        week_id=week_id,
        path=str(out_path),
        main_feed_count=total_main,
        also_seen_count=len(also_seen),
        pipeline_notice_pending=pipeline_notice_pending_count,
        pipeline_notice_failed=pipeline_notice_failed_source_count,
    )
    return out_path


__all__ = ["DigestCard", "render_digest"]
