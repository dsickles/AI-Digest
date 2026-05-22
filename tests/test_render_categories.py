"""Renderer tests for per-category section grouping (PIPELINE-02)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pipeline.render.html import CATEGORY_LABELS, DigestCard, render_digest


def _card(
    *,
    title: str,
    category: str | None,
    published_at: datetime,
    tldr: str = "Summary text.",
) -> DigestCard:
    return DigestCard(
        title=title,
        publisher="Test Source",
        canonical_url=f"https://example.com/{title.replace(' ', '-').lower()}",
        published_at=published_at,
        tldr=tldr,
        summary_confidence="high",
        summary_status="ok",
        category=category,
    )


def test_two_categories_render_two_sections(tmp_path: Path) -> None:
    cards = [
        _card(
            title="Tech story",
            category="technical",
            published_at=datetime(2026, 5, 21, tzinfo=UTC),
        ),
        _card(
            title="Business story",
            category="business",
            published_at=datetime(2026, 5, 20, tzinfo=UTC),
        ),
    ]
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert body.count('class="category-section"') == 2
    assert 'data-category="technical"' in body
    assert 'data-category="business"' in body
    assert f">{CATEGORY_LABELS['technical']}<" in body
    assert f">{CATEGORY_LABELS['business']}<" in body


def test_category_header_title_case_not_enum_code(tmp_path: Path) -> None:
    cards = [
        _card(
            title="Only technical",
            category="technical",
            published_at=datetime(2026, 5, 21, tzinfo=UTC),
        ),
    ]
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "Technical" in body
    assert 'class="category-header">technical<' not in body


def test_cards_not_outside_category_sections(tmp_path: Path) -> None:
    """Main-feed cards live inside category-section blocks only."""
    cards = [
        _card(
            title="Tech A",
            category="technical",
            published_at=datetime(2026, 5, 22, tzinfo=UTC),
        ),
        _card(
            title="Design B",
            category="design",
            published_at=datetime(2026, 5, 21, tzinfo=UTC),
        ),
    ]
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    main_start = body.index("<main>")
    main_end = body.index("</main>")
    main_html = body[main_start:main_end]
    assert main_html.count('<article class="card">') == 2
    assert "category-section" in main_html
    assert main_html.index("category-section") < main_html.index("Tech A")


def test_no_category_badge_on_individual_cards(tmp_path: Path) -> None:
    cards = [
        _card(
            title="Card",
            category="technical",
            published_at=datetime(2026, 5, 21, tzinfo=UTC),
        ),
    ]
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert 'class="card"' in body
    assert "category-badge" not in body
    card_slice = body.split('<article class="card">', 1)[1].split("</article>", 1)[0]
    assert "data-category" not in card_slice


def test_footer_also_seen_still_present(tmp_path: Path) -> None:
    thin = DigestCard(
        title="Thin item",
        publisher="Test",
        canonical_url="https://example.com/thin",
        published_at=datetime(2026, 5, 21, tzinfo=UTC),
        tldr=None,
        summary_confidence="unavailable",
        summary_status="thin",
        category="business",
    )
    healthy = _card(
        title="Healthy",
        category="technical",
        published_at=datetime(2026, 5, 22, tzinfo=UTC),
    )
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[healthy, thin],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert '<aside id="also-seen">' in body
    assert "Thin item" in body
