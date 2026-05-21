"""HTML renderer tests — partition behavior + escape safety."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pipeline.render.html import DigestCard, render_digest


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


def test_displayed_and_omitted_are_partitioned(tmp_path: Path) -> None:
    """Cards with tldr render as articles; tldr=None go to the footer."""
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

    assert '<article class="card">' in body
    assert body.count('<article class="card">') == 2, "expected 2 displayed cards"
    assert "Real Article" in body
    assert "Another Real Post" in body
    assert "Also seen this week" in body
    assert "Release Notes 0.1a0" in body
    assert "1 item omitted" in body
    assert "2 items" in body


def test_only_thin_items_renders_helpful_empty_state(tmp_path: Path) -> None:
    """When every card is omitted, main shows the empty-state message + footer list."""
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
    assert '<article class="card">' not in body
    assert "Every item this week was a release-note" in body
    assert "Notes A" in body and "Notes B" in body
    assert "0 items" in body


def test_omitted_links_use_target_blank_noopener(tmp_path: Path) -> None:
    """Footer links must carry target=_blank rel=noopener (D-16)."""
    cards = [
        _card(title="Real Article"),
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


def test_no_pipeline_notes_when_nothing_omitted(tmp_path: Path) -> None:
    """If every card has a tldr, the 'Also seen this week' section is absent."""
    cards = [_card(title="Real")]
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 11, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "Also seen this week" not in body
    assert "1 item" in body


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
