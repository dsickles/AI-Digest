"""HTML renderer tests — degraded inline cards + escape safety."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from pipeline.render.html import DEGRADED_SUMMARY_LINE, DigestCard, render_digest


def _card(
    *,
    title: str = "Test Title",
    publisher: str = "Test Publisher",
    url: str = "https://example.com/post",
    tldr: str | None = "A short summary.",
    confidence: str = "high",
    published_at: datetime | None = None,
) -> DigestCard:
    return DigestCard(
        title=title,
        publisher=publisher,
        canonical_url=url,
        published_at=published_at or datetime(2026, 5, 18, tzinfo=UTC),
        tldr=tldr,
        summary_confidence=confidence,
    )


def test_header_contains_week_of(tmp_path: Path) -> None:
    """D-18: header shows Week of Mon – Sun range from week_bounds."""
    cards = [_card(title="Real")]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "Week of" in body
    assert "May 4" in body
    assert "May 10, 2026" in body
    assert "Updated 20" in body
    assert "<h1>AI Digest</h1>" in body


def test_all_anchor_tags_have_rel_noopener(tmp_path: Path) -> None:
    """D-16: every external link carries rel=noopener."""
    cards = [
        _card(title="First", url="https://a.example/post"),
        _card(title="Second", url="https://b.example/post", tldr=None, confidence="unavailable"),
    ]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    anchors = re.findall(r"<a\b[^>]*>", body)
    assert len(anchors) >= 2
    for tag in anchors:
        assert 'rel="noopener"' in tag
        assert 'target="_blank"' in tag


def test_cards_sorted_newest_first(tmp_path: Path) -> None:
    """Cards render in published_at descending order."""
    cards = [
        _card(title="Older", published_at=datetime(2026, 5, 5, tzinfo=UTC)),
        _card(title="Newer", published_at=datetime(2026, 5, 9, tzinfo=UTC)),
    ]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert body.index("Newer") < body.index("Older")


def test_source_badge_bracketed_display_name(tmp_path: Path) -> None:
    """D-14: publisher badge uses [display_name] format."""
    cards = [_card(publisher="Simon Willison")]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "[Simon Willison]" in body


def test_degraded_card(tmp_path: Path) -> None:
    """Degraded items render inline with the D-05 sentinel line (D-15)."""
    cards = [
        _card(title='AT&T "scoop" & more', tldr=None, confidence="unavailable"),
    ]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")

    assert DEGRADED_SUMMARY_LINE in body
    assert body.count('<article class="card">') == 1
    assert "AT&amp;T" in body
    assert "&quot;scoop&quot;" in body
    assert 'target="_blank" rel="noopener"' in body
    assert "Also seen this week" not in body


def test_mixed_cards_all_render_inline(tmp_path: Path) -> None:
    """Summarized and degraded items both appear as full cards."""
    cards = [
        _card(title="Real Article"),
        _card(title="Release Notes 0.1a0", tldr=None, confidence="unavailable"),
        _card(title="Another Real Post"),
    ]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")

    assert body.count('<article class="card">') == 3
    assert "Real Article" in body
    assert "Release Notes 0.1a0" in body
    assert "Another Real Post" in body
    assert DEGRADED_SUMMARY_LINE in body


def test_only_thin_items_still_render_cards(tmp_path: Path) -> None:
    """When every card is degraded, each still renders as a full article card."""
    cards = [
        _card(title="Notes A", tldr=None, confidence="unavailable"),
        _card(title="Notes B", tldr=None, confidence="unavailable"),
    ]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert body.count('<article class="card">') == 2
    assert "Notes A" in body and "Notes B" in body
    assert body.count(DEGRADED_SUMMARY_LINE) == 2


def test_degraded_link_uses_target_blank_noopener(tmp_path: Path) -> None:
    """Card title links must carry target=_blank rel=noopener (D-16)."""
    cards = [
        _card(
            title="Skipped",
            url="https://example.com/skipped",
            tldr=None,
            confidence="unavailable",
        ),
    ]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert (
        '<a href="https://example.com/skipped" target="_blank" rel="noopener">'
        in body
    )


def test_all_summarized_cards(tmp_path: Path) -> None:
    """Digest renders summarized cards without degraded sentinel."""
    cards = [_card(title="Real")]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert DEGRADED_SUMMARY_LINE not in body
    assert "Real" in body


def test_html_escapes_user_strings(tmp_path: Path) -> None:
    """T-01-02: titles/summaries with HTML-special chars are escaped."""
    cards = [
        _card(title="Foo <script>alert(1)</script>"),
        _card(
            title='AT&T "scoop"',
            tldr=None,
            confidence="unavailable",
        ),
    ]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "AT&amp;T" in body
    assert "&quot;scoop&quot;" in body
