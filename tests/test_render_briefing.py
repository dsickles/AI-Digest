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
