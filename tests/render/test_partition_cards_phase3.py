"""LOCKED-01 partition routing regression tests for Phase 3 (Wave 0)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pipeline.render.html import QUOTA_BODY_COPY, DigestCard, render_digest


def _card(
    *,
    tldr: str | None,
    summary_status: str | None,
    title: str = "Story",
) -> DigestCard:
    return DigestCard(
        title=title,
        publisher="Example Publisher",
        canonical_url="https://example.com/post",
        published_at=datetime(2026, 5, 20, tzinfo=UTC),
        tldr=tldr,
        summary_confidence="unavailable" if not tldr else "high",
        summary_status=summary_status,
    )


def _render_single(card: DigestCard, tmp_path: Path) -> str:
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[card],
        out_dir=tmp_path,
    )
    return out.read_text(encoding="utf-8")


def test_thin_status_routes_to_footer_aside(tmp_path: Path) -> None:
    body = _render_single(_card(tldr=None, summary_status="thin"), tmp_path)
    assert '<aside id="also-seen">' in body
    assert "Story" in body.split('<aside id="also-seen">')[1]
    main_section = body.split("<main>")[1].split("</main>")[0]
    assert "card-title" not in main_section or "Also seen" in main_section


def test_quota_exhausted_stays_in_main_feed_with_copy(tmp_path: Path) -> None:
    body = _render_single(_card(tldr=None, summary_status="quota_exhausted"), tmp_path)
    assert QUOTA_BODY_COPY in body
    main_section = body.split("<main>")[1].split("</main>")[0]
    assert QUOTA_BODY_COPY in main_section
    assert '<aside id="also-seen">' not in body


def test_non_quota_errors_route_to_footer_not_main(tmp_path: Path) -> None:
    for status in ("api_error", "parse_error", "client_init_error"):
        body = _render_single(
            _card(tldr=None, summary_status=status, title=f"Err {status}"),
            tmp_path,
        )
        assert '<aside id="also-seen">' in body
        footer = body.split('<aside id="also-seen">')[1]
        assert f"Err {status}" in footer
        main_section = body.split("<main>")[1].split("</main>")[0]
        assert f"Err {status}" not in main_section
