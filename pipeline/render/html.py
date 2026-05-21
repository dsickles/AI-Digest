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
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
  background: #0b0d10;
  color: #e6e8eb;
  line-height: 1.55;
}
header {
  padding: 32px 24px 16px;
  border-bottom: 1px solid #1d2229;
  background: linear-gradient(180deg, #0f1419 0%, #0b0d10 100%);
}
header h1 { margin: 0; font-size: 1.6rem; letter-spacing: -0.01em; }
header p  { margin: 4px 0 0; color: #8a93a0; font-size: 0.95rem; }
main { max-width: 760px; margin: 0 auto; padding: 24px; }
.card {
  border: 1px solid #1d2229;
  border-radius: 10px;
  padding: 20px 22px;
  margin-bottom: 16px;
  background: #11151a;
}
.card-meta {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 0.85rem;
  color: #8a93a0;
  margin-bottom: 6px;
}
.publisher-badge {
  background: #1f2630;
  color: #b9c2cf;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.78rem;
  letter-spacing: 0.01em;
}
.card-title { margin: 0 0 10px; font-size: 1.15rem; }
.card-title a { color: #e6e8eb; text-decoration: none; }
.card-title a:hover { color: #6cb2ff; text-decoration: underline; }
.card-tldr { margin: 0; color: #c8cdd5; }
.degraded {
  font-style: italic;
  color: #8a93a0;
}
.pipeline-notes {
  margin-top: 32px;
  padding: 18px 22px;
  border: 1px dashed #1d2229;
  border-radius: 10px;
  background: #0f1318;
  font-size: 0.88rem;
  color: #8a93a0;
}
.pipeline-notes h3 {
  margin: 0 0 8px;
  font-size: 0.92rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #b9c2cf;
  font-weight: 600;
}
.pipeline-notes p { margin: 0; line-height: 1.6; }
.pipeline-notes a {
  color: #b9c2cf;
  text-decoration: none;
  border-bottom: 1px dotted #4a5260;
}
.pipeline-notes a:hover { color: #6cb2ff; border-bottom-color: #6cb2ff; }
.pipeline-notes .sep { color: #4a5260; margin: 0 6px; }
footer {
  padding: 20px 24px;
  text-align: center;
  color: #5d6571;
  font-size: 0.8rem;
  border-top: 1px solid #1d2229;
  margin-top: 24px;
}
""".strip()


def _format_date(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d")


def _render_card(card: DigestCard) -> str:
    title_safe = html.escape(card.title)
    publisher_safe = html.escape(card.publisher)
    url_safe = html.escape(card.canonical_url, quote=True)
    date_safe = html.escape(_format_date(card.published_at))

    if card.tldr:
        tldr_html = f'<p class="card-tldr">{html.escape(card.tldr)}</p>'
    else:
        tldr_html = (
            '<p class="card-tldr degraded">'
            "Summary unavailable — content was too thin to summarize. "
            "Open the source link to read the original."
            "</p>"
        )

    return (
        '<article class="card">'
        '<div class="card-meta">'
        f'<span class="publisher-badge">{publisher_safe}</span>'
        f"<span>{date_safe}</span>"
        "</div>"
        '<h2 class="card-title">'
        f'<a href="{url_safe}" target="_blank" rel="noopener">{title_safe}</a>'
        "</h2>"
        f"{tldr_html}"
        "</article>"
    )


def _is_displayable(card: DigestCard) -> bool:
    """A card is rendered as a full article only when it has a real summary."""
    return card.tldr is not None and card.summary_confidence != "unavailable"


def _render_omitted_link(card: DigestCard) -> str:
    """Render one omitted item as an inline title-only clickable link."""
    title_safe = html.escape(card.title)
    url_safe = html.escape(card.canonical_url, quote=True)
    return f'<a href="{url_safe}" target="_blank" rel="noopener">{title_safe}</a>'


def _render_pipeline_notes(omitted: list[DigestCard]) -> str:
    """'Also seen this week' footer section listing skipped items as links."""
    if not omitted:
        return ""

    count = len(omitted)
    label = "item" if count == 1 else "items"
    links = '<span class="sep">·</span>'.join(
        _render_omitted_link(card) for card in omitted
    )
    return (
        '<aside class="pipeline-notes" aria-label="Pipeline notes">'
        "<h3>Also seen this week</h3>"
        f"<p>{count} {label} omitted from the digest "
        "(no body content to summarize): "
        f"{links}"
        "</p>"
        "</aside>"
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

    Cards with ``tldr is None`` (or ``summary_confidence == 'unavailable'``)
    are NOT rendered as full articles — they appear as a single
    "Also seen this week" footer section with title-only links so the
    reader can still see them without paying scroll-tax for empty cards.
    """
    out_root = out_dir or DEFAULT_OUT_DIR
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"digest-{week_id}.html"

    displayed = [c for c in cards if _is_displayable(c)]
    omitted = [c for c in cards if not _is_displayable(c)]

    week_label_safe = html.escape(week_id)
    range_safe = html.escape(
        f"{_format_date(week_start)} → {_format_date(week_end)}"
    )
    generated_safe = html.escape(
        datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    )

    if displayed:
        cards_html = "\n".join(_render_card(card) for card in displayed)
    elif omitted:
        cards_html = (
            '<p class="degraded">'
            "Every item this week was a release-note or had no body content "
            "to summarize. See the list below for source links."
            "</p>"
        )
    else:
        cards_html = (
            '<p class="degraded">'
            "No items found for this week. Either no enabled source published "
            "anything in the window, or all entries were skipped due to missing "
            "publication dates."
            "</p>"
        )

    notes_html = _render_pipeline_notes(omitted)

    displayed_count = len(displayed)
    item_word = "item" if displayed_count == 1 else "items"

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Digest — {week_label_safe}</title>
<style>
{_CSS}
</style>
</head>
<body>
<header>
  <h1>AI Digest — {week_label_safe}</h1>
  <p>{range_safe} · {displayed_count} {item_word}</p>
</header>
<main>
{cards_html}
{notes_html}
</main>
<footer>
  Generated {generated_safe} · Phase 1 walking skeleton
</footer>
</body>
</html>
"""

    out_path.write_text(document, encoding="utf-8")
    logger.info(
        "render.digest.written",
        path=str(out_path),
        week_id=week_id,
        displayed=displayed_count,
        omitted=len(omitted),
    )
    return out_path


__all__ = ["DigestCard", "render_digest"]
