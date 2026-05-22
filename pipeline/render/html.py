"""Phase 2 in-place plain-HTML digest renderer (D-25 / D-26 / D-24 / D-30).

D-25 supersedes Phase 1 D-05: every digest item renders as ``<article
class="card">`` in natural sort position regardless of summary state.
Degraded cards (transcript pending, captions missing, thin source body,
enrichment or LLM failure) carry a plain-English ``degradation_reason``
in place of the TL;DR. There is no footer aside, no "Also seen this week"
heading, and no ``pipeline-notes`` block — those Phase 1 surfaces are gone.

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


@dataclass(frozen=True)
class DigestCard:
    """One card in the digest. Built by the orchestrator from items + summaries.

    D-25 extension: ``source_type``, ``transcript_status``, and
    ``degradation_reason`` make the card self-describing so the renderer
    never has to reach back into the adapter or the items table.
    """

    title: str
    publisher: str
    canonical_url: str
    published_at: datetime
    tldr: str | None
    summary_confidence: str  # 'high' | 'low' | 'unavailable'
    source_type: str = "rss"  # D-30 routes video indicator
    transcript_status: str | None = None  # D-23 lifecycle; informational here
    degradation_reason: str | None = None  # D-25 plain-English body for degraded cards


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


def _is_degraded(card: DigestCard) -> bool:
    """A card is degraded when there is no usable summary or a degradation reason is set."""
    if card.degradation_reason is not None:
        return True
    if card.tldr is None:
        return True
    return card.summary_confidence == "unavailable"


def _render_body(card: DigestCard) -> str:
    """D-25 body copy: plain-English degradation_reason for degraded cards,
    TL;DR paragraph for healthy ones. Empty body is rendered as an empty
    paragraph so the card footprint stays uniform. ``quote=False`` keeps
    apostrophes readable inside text content; ``<``, ``>``, ``&`` still
    escape, mitigating T-02-01 (untrusted strings reaching the browser).
    """
    if _is_degraded(card):
        reason = card.degradation_reason or "This item couldn't be summarized this week."
        return f'<p class="card-degraded">{html.escape(reason, quote=False)}</p>'
    return f'<p class="card-tldr">{html.escape(card.tldr or "", quote=False)}</p>'


def _render_card(card: DigestCard) -> str:
    title_safe = html.escape(card.title)
    badge_safe = html.escape(f"[{card.publisher}]")
    url_safe = html.escape(card.canonical_url, quote=True)
    date_safe = html.escape(_format_date(card.published_at))

    if card.source_type == "youtube":
        # D-30: keep the indicator structurally minimal — same span height, no glyph deps.
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
    """Write the weekly digest HTML and return the output path (D-25, D-26).

    Every card renders as an ``<article class="card">`` in natural
    published_at-descending order; degraded cards keep their slot and
    display a plain-English ``degradation_reason``. The header pipeline
    notice (D-26) appears only when ``pipeline_notice_pending_count`` or
    ``pipeline_notice_failed_source_count`` is positive.
    """
    out_root = out_dir or DEFAULT_OUT_DIR
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"digest-{week_id}.html"

    sorted_cards = sorted(cards, key=lambda c: c.published_at, reverse=True)

    week_header = _format_week_header(week_start, week_end)
    updated_line = _format_updated(datetime.now(UTC))
    notice_html = _render_pipeline_notice(
        pending=pipeline_notice_pending_count,
        failed_sources=pipeline_notice_failed_source_count,
    )

    week_header_safe = html.escape(week_header)
    updated_safe = html.escape(updated_line)

    if sorted_cards:
        cards_html = "\n".join(_render_card(card) for card in sorted_cards)
    else:
        cards_html = (
            '<p class="card-degraded">'
            "No items found for this week. Either no enabled source published "
            "anything in the window, or all entries were skipped due to missing "
            "publication dates."
            "</p>"
        )

    total_count = len(sorted_cards)
    item_word = "item" if total_count == 1 else "items"
    header_count_line = f"{total_count} {item_word}"

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
</body>
</html>
"""

    out_path.write_text(document, encoding="utf-8")
    degraded_count = sum(1 for c in sorted_cards if _is_degraded(c))
    logger.info(
        "render_complete",
        week_id=week_id,
        path=str(out_path),
        card_count=total_count,
        degraded_count=degraded_count,
        pipeline_notice_pending=pipeline_notice_pending_count,
        pipeline_notice_failed=pipeline_notice_failed_source_count,
    )
    return out_path


__all__ = ["DigestCard", "render_digest"]
