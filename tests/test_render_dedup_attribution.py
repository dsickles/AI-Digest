"""Renderer tests for cluster attribution (D-64)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pipeline.render.html import (
    ALSO_COVERED_PREFIX,
    AlsoCoveredMember,
    DigestCard,
    render_digest,
)


def _card(
    *,
    title: str = "Canonical story",
    also_covered: tuple[AlsoCoveredMember, ...] = (),
    tldr: str = "Summary text.",
) -> DigestCard:
    return DigestCard(
        title=title,
        publisher="Canonical Source",
        canonical_url="https://example.com/canonical",
        published_at=datetime(2026, 5, 20, tzinfo=UTC),
        tldr=tldr,
        summary_confidence="high",
        summary_status="ok",
        also_covered=also_covered,
    )


def test_three_member_cluster_renders_also_covered(tmp_path: Path) -> None:
    members = (
        AlsoCoveredMember(display_name="Source B", url="https://example.com/b"),
        AlsoCoveredMember(display_name='Source "C"', url="https://example.com/c"),
    )
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[_card(also_covered=members)],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert ALSO_COVERED_PREFIX.strip() in body
    assert 'class="also-covered-by"' in body
    assert "Source B" in body
    assert "Source &quot;C&quot;" in body


def test_single_member_cluster_omits_also_covered(tmp_path: Path) -> None:
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[_card(also_covered=())],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert 'class="also-covered-by"' not in body
