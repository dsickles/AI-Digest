"""Renderer tests for weekly synthesis and category mini rollups (PIPELINE-04)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from pipeline.render.html import (
    WEEKLY_ROLLUP_FAILURE_COPY,
    DigestCard,
    render_digest,
)


def _rollup_row(*, scope: str, narrative_md: str | None, rollup_status: str):
    return SimpleNamespace(
        scope=scope,
        narrative_md=narrative_md,
        rollup_status=rollup_status,
    )


def _card(*, title: str, category: str = "technical") -> DigestCard:
    return DigestCard(
        title=title,
        publisher="Test Source",
        canonical_url=f"https://example.com/{title.replace(' ', '-').lower()}",
        published_at=datetime(2026, 5, 21, tzinfo=UTC),
        tldr="Summary text.",
        summary_confidence="high",
        summary_status="ok",
        category=category,
        rank_position=1,
    )


def test_ok_weekly_renders_weekly_synthesis_body(tmp_path: Path) -> None:
    rollups = {
        "weekly": _rollup_row(
            scope="weekly",
            narrative_md="The week centered on inference pricing cuts.",
            rollup_status="ok",
        )
    }
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[_card(title="Top story")],
        out_dir=tmp_path,
        rollups_by_scope=rollups,
    )
    body = out.read_text(encoding="utf-8")
    assert 'class="weekly-synthesis-body"' in body
    assert "inference pricing cuts" in body


def test_failed_weekly_renders_rollup_failure_notice(tmp_path: Path) -> None:
    rollups = {
        "weekly": _rollup_row(
            scope="weekly",
            narrative_md=None,
            rollup_status="api_error",
        )
    }
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[_card(title="Top story")],
        out_dir=tmp_path,
        rollups_by_scope=rollups,
    )
    body = out.read_text(encoding="utf-8")
    assert 'class="rollup-failure-notice"' in body
    assert "narrative roll-up couldn't be generated" in body
    assert "Top 5 stories are below" in body


def test_failed_category_mini_still_renders_cards_without_mini_paragraph(
    tmp_path: Path,
) -> None:
    rollups = {
        "weekly": _rollup_row(
            scope="weekly",
            narrative_md="Weekly note.",
            rollup_status="ok",
        ),
        "category:technical": _rollup_row(
            scope="category:technical",
            narrative_md=None,
            rollup_status="api_error",
        ),
    }
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[_card(title="Technical story", category="technical")],
        out_dir=tmp_path,
        rollups_by_scope=rollups,
    )
    body = out.read_text(encoding="utf-8")
    assert 'class="card"' in body
    assert 'class="category-mini-rollup"' not in body


def test_weekly_synthesis_precedes_briefing(tmp_path: Path) -> None:
    rollups = {
        "weekly": _rollup_row(
            scope="weekly",
            narrative_md="Editor weekly note.",
            rollup_status="ok",
        )
    }
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[_card(title="Briefing lead")],
        out_dir=tmp_path,
        rollups_by_scope=rollups,
    )
    body = out.read_text(encoding="utf-8")
    assert body.index('class="weekly-synthesis"') < body.index('class="briefing"')


def test_weekly_rollup_failure_copy_has_no_cli_syntax() -> None:
    assert "--" not in WEEKLY_ROLLUP_FAILURE_COPY
    assert "RuntimeError" not in WEEKLY_ROLLUP_FAILURE_COPY
    assert "python -m" not in WEEKLY_ROLLUP_FAILURE_COPY
