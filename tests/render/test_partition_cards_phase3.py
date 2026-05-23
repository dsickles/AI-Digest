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


def test_non_thin_failures_render_in_place_in_main(tmp_path: Path) -> None:
    """LOCKED-01 (2026-05-23 refinement): every non-thin failure status
    renders as an in-place degraded card in the main feed, not the footer.

    The footer is now reserved for `thin` only (RSS body too short).
    """
    for status in (
        "quota_exhausted",
        "api_error",
        "parse_error",
        "client_init_error",
        "transcript_missing",
    ):
        body = _render_single(
            _card(tldr=None, summary_status=status, title=f"InPlace {status}"),
            tmp_path,
        )
        main_section = body.split("<main>")[1].split("</main>")[0]
        assert f"InPlace {status}" in main_section, (
            f"{status} must render in main feed, not footer"
        )
        assert QUOTA_BODY_COPY in main_section, (
            f"{status} must use the locked degraded body copy"
        )
        # No footer expected for any of these single-card cases.
        assert '<aside id="also-seen">' not in body, (
            f"{status} must not appear in #also-seen footer"
        )


def test_thin_is_the_only_footer_status(tmp_path: Path) -> None:
    """Mixed-status render: 'thin' lands in footer, everything else in main."""
    cards = [
        _card(tldr="Real summary text.", summary_status="ok", title="Healthy"),
        _card(tldr=None, summary_status="thin", title="ThinRss"),
        _card(tldr=None, summary_status="quota_exhausted", title="Quota"),
        _card(tldr=None, summary_status="api_error", title="ApiErr"),
        _card(tldr=None, summary_status="transcript_missing", title="Transcript"),
    ]
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    main_section = body.split("<main>")[1].split("</main>")[0]
    footer_section = body.split('<aside id="also-seen">')[1] if '<aside id="also-seen">' in body else ""

    for title in ("Healthy", "Quota", "ApiErr", "Transcript"):
        assert title in main_section
        assert title not in footer_section
    assert "ThinRss" in footer_section
    assert "ThinRss" not in main_section
