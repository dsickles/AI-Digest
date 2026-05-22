"""Phase 1 plain-HTML digest renderer (D-17 dark-bg seed).

Deliberately simple: no templating engine, no asset pipeline, no
framework. Phase 4 replaces this with the Astro dashboard. All
user-derived strings (title, publisher, summary) flow through
``html.escape`` to mitigate T-01-02 (untrusted RSS content reaching
the browser).

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
DEGRADED_SUMMARY_LINE = "[summary unavailable — content too thin]"


@dataclass(frozen=True)
class DigestCard:
    """One card in the digest. Built by the orchestrator from items + summaries."""

    title: str
    publisher: str
    canonical_url: str
    published_at: datetime
    tldr: str | None
    summary_confidence: str  # 'high' | 'low' | 'unavailable'


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
.card-title { margin: 0 0 0.55rem; font-size: 1.1rem; line-height: 1.35; }
.card-title a { color: #e6e6e6; text-decoration: none; }
.card-title a:hover { color: #7eb6ff; text-decoration: underline; }
.card-tldr { margin: 0; color: #c8cdd5; }
.degraded { font-style: italic; color: #9aa3b2; }
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


def _render_card(card: DigestCard) -> str:
    title_safe = html.escape(card.title)
    badge_safe = html.escape(f"[{card.publisher}]")
    url_safe = html.escape(card.canonical_url, quote=True)
    date_safe = html.escape(_format_date(card.published_at))

    is_degraded = card.tldr is None or card.summary_confidence == "unavailable"
    if is_degraded:
        tldr_html = (
            f'<p class="card-tldr degraded">{html.escape(DEGRADED_SUMMARY_LINE)}</p>'
        )
    else:
        tldr_html = f'<p class="card-tldr">{html.escape(card.tldr or "")}</p>'

    return (
        '<article class="card">'
        '<div class="card-meta">'
        f'<span class="source-badge">{badge_safe}</span>'
        f"<span>{date_safe}</span>"
        "</div>"
        '<h2 class="card-title">'
        f'<a href="{url_safe}" target="_blank" rel="noopener">{title_safe}</a>'
        "</h2>"
        f"{tldr_html}"
        "</article>"
    )


def render_digest(
    *,
    week_id: str,
    week_start: datetime,
    week_end: datetime,
    cards: list[DigestCard],
    out_dir: Path | None = None,
) -> Path:
    """Write the weekly digest HTML and return the output path.

    Cards should be sorted newest-first by the caller; we sort again as
    a safety net. Degraded summaries show the D-05 sentinel inline.
    """
    out_root = out_dir or DEFAULT_OUT_DIR
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"digest-{week_id}.html"

    sorted_cards = sorted(cards, key=lambda c: c.published_at, reverse=True)
    week_header = _format_week_header(week_start, week_end)
    updated_line = _format_updated(datetime.now(UTC))

    week_header_safe = html.escape(week_header)
    updated_safe = html.escape(updated_line)

    if sorted_cards:
        cards_html = "\n".join(_render_card(card) for card in sorted_cards)
    else:
        cards_html = (
            '<p class="degraded">'
            "No items found for this week. Either no enabled source published "
            "anything in the window, or all entries were skipped due to missing "
            "publication dates."
            "</p>"
        )

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
  <p class="week-range">{week_header_safe}</p>
  <p class="updated">{updated_safe}</p>
</header>
<main>
{cards_html}
</main>
</body>
</html>
"""

    out_path.write_text(document, encoding="utf-8")
    logger.info(
        "render_complete",
        week_id=week_id,
        path=str(out_path),
        card_count=len(sorted_cards),
    )
    return out_path


__all__ = ["DigestCard", "render_digest"]
