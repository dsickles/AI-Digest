"""HTML renderer tests — degraded inline cards + escape safety."""
from __future__ import annotations

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
) -> DigestCard:
    return DigestCard(
        title=title,
        publisher=publisher,
        canonical_url=url,
        published_at=datetime(2026, 5, 18, tzinfo=UTC),
        tldr=tldr,
        summary_confidence=confidence,
    )


def test_degraded_card(tmp_path: Path) -> None:
    """Degraded items render inline with the D-05 sentinel line (D-15)."""
    cards = [
        _card(title='AT&T "scoop" & more', tldr=None, confidence="unavailable"),
    ]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 11, tzinfo=UTC),
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
        week_end=datetime(2026, 5, 11, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")

    assert body.count('<article class="card">') == 3
    assert "Real Article" in body
    assert "Release Notes 0.1a0" in body
    assert "Another Real Post" in body
    assert DEGRADED_SUMMARY_LINE in body
    assert "3 items" in body


def test_only_thin_items_still_render_cards(tmp_path: Path) -> None:
    """When every card is degraded, each still renders as a full article card."""
    cards = [
        _card(title="Notes A", tldr=None, confidence="unavailable"),
        _card(title="Notes B", tldr=None, confidence="unavailable"),
    ]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 11, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert body.count('<article class="card">') == 2
    assert "Notes A" in body and "Notes B" in body
    assert body.count(DEGRADED_SUMMARY_LINE) == 2
    assert "2 items" in body


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
        week_end=datetime(2026, 5, 11, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert (
        '<a href="https://example.com/skipped" target="_blank" rel="noopener">'
        in body
    )


def test_all_summarized_cards(tmp_path: Path) -> None:
    """Digest header reflects total card count."""
    cards = [_card(title="Real")]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 11, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "1 item" in body
    assert DEGRADED_SUMMARY_LINE not in body


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
        week_end=datetime(2026, 5, 11, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "AT&amp;T" in body
    assert "&quot;scoop&quot;" in body
