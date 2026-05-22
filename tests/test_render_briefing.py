"""Renderer tests for rank-ordered category sections (PIPELINE-03 partial)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pipeline.render.html import DigestCard, render_digest


def _card(
    *,
    title: str,
    category: str,
    rank_position: int | None,
    published_at: datetime,
) -> DigestCard:
    return DigestCard(
        title=title,
        publisher="Test Source",
        canonical_url=f"https://example.com/{title.replace(' ', '-').lower()}",
        published_at=published_at,
        tldr="Summary text.",
        summary_confidence="high",
        summary_status="ok",
        category=category,
        rank_position=rank_position,
    )


def test_category_section_orders_by_rank_position_not_recency(tmp_path: Path) -> None:
    """Higher global rank (lower rank_position) appears before lower rank in section."""
    cards = [
        _card(
            title="Lower rank newer",
            category="technical",
            rank_position=5,
            published_at=datetime(2026, 5, 22, tzinfo=UTC),
        ),
        _card(
            title="Higher rank older",
            category="technical",
            rank_position=2,
            published_at=datetime(2026, 5, 18, tzinfo=UTC),
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
    assert body.index("Higher rank older") < body.index("Lower rank newer")


def test_briefing_section_top_five_from_ten_ranked_clusters(tmp_path: Path) -> None:
    """DISPLAY-03: numbered Briefing with exactly top_n_briefing items (default 5)."""
    categories = ("edtech", "business", "technical", "design")
    cards = [
        DigestCard(
            title=f"Story {index}",
            publisher="Test Source",
            canonical_url=f"https://example.com/story-{index}",
            published_at=datetime(2026, 5, 18 + (index % 5), tzinfo=UTC),
            tldr=f"Summary for story {index}.",
            summary_confidence="high",
            summary_status="ok",
            category=categories[index % 4],
            rank_position=index,
        )
        for index in range(1, 11)
    ]
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert 'class="briefing-header">Briefing — Top 5 this week<' in body
    assert body.count('class="briefing-item"') == 5
    assert 'class="briefing-list"' in body
    assert "Story 1" in body
    assert "Story 5" in body
    assert "Story 6" not in body.split("</section>", 1)[0]


def test_briefing_precedes_category_sections(tmp_path: Path) -> None:
    cards = [
        DigestCard(
            title="Top story",
            publisher="Test",
            canonical_url="https://example.com/top",
            published_at=datetime(2026, 5, 21, tzinfo=UTC),
            tldr="Top summary.",
            summary_confidence="high",
            summary_status="ok",
            category="technical",
            rank_position=1,
        ),
        DigestCard(
            title="Category filler",
            publisher="Test",
            canonical_url="https://example.com/filler",
            published_at=datetime(2026, 5, 20, tzinfo=UTC),
            tldr="Filler summary.",
            summary_confidence="high",
            summary_status="ok",
            category="business",
            rank_position=2,
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
    assert body.index('class="briefing"') < body.index('class="category-section"')
    assert 'class="card briefing-card"' in body
