"""HTML renderer tests — PROJECT.md LOCKED-01 footer-aside contract.

The locked rule (2026-05-22, refined 2026-05-23):

* **Footer (``<aside id="also-seen">``) — RSS-thin only.** A card routes
  to the footer iff ``summary_status='thin'`` (RSS body too short).
* **Main feed — everything else.** Healthy cards render as full cards;
  the in-place degraded bucket (``quota_exhausted``, ``api_error``,
  ``parse_error``, ``client_init_error``, ``transcript_missing``) renders
  in-place with the locked body
  ``"The summary couldn't be generated this week."``.

The 2026-05-23 refinement narrowed the footer (previously held all
"couldn't summarize" reasons) so that long-form videos with successful
transcripts but failed summarize calls keep their context (publisher,
video badge, date, category) instead of dropping into the link-only
footer next to genuinely-thin RSS stubs.

History (do not bring back):
- Plan 01-03 inline-regressed the footer once; reverted 5f8e9f0.
- Plan 02-03 D-25 tried to remove the footer again ("in-place degradation,
  no relegation") and was rejected during Phase 2 visual UAT.
- 2026-05-22 lock briefly kept api_error / pending_local in the footer;
  the 2026-05-23 Phase 3 visual UAT moved them to in-place degraded.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from pipeline.render.html import (
    QUOTA_BODY_COPY,
    VIDEO_INDICATOR,
    DigestCard,
    render_digest,
)


def _card(
    *,
    title: str = "Test Title",
    publisher: str = "Test Publisher",
    url: str = "https://example.com/post",
    tldr: str | None = "A short summary.",
    confidence: str = "high",
    published_at: datetime | None = None,
    source_type: str = "rss",
    transcript_status: str | None = None,
    summary_status: str | None = "ok",
) -> DigestCard:
    return DigestCard(
        title=title,
        publisher=publisher,
        canonical_url=url,
        published_at=published_at or datetime(2026, 5, 18, tzinfo=UTC),
        tldr=tldr,
        summary_confidence=confidence,
        source_type=source_type,
        transcript_status=transcript_status,
        summary_status=summary_status,
    )


# ---------------------------------------------------------------------------
# Header + structural assertions
# ---------------------------------------------------------------------------


def test_header_contains_week_of(tmp_path: Path) -> None:
    """D-18: header shows Week of Mon – Sun range from week_bounds."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, 23, 59, 59, tzinfo=UTC),
        cards=[_card(title="Real")],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "Week of May 4 – May 10, 2026" in body


def test_header_item_count_reflects_main_feed_only(tmp_path: Path) -> None:
    """Header item count is the *main feed* size; footer items are summed
    separately as a suffix so the reader sees both numbers without
    pretending the footer items contribute to the curated total."""
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[
            _card(title="Real one", tldr="real", summary_status="ok"),
            _card(
                title="Real two",
                tldr="real",
                summary_status="ok",
                published_at=datetime(2026, 5, 19, tzinfo=UTC),
            ),
            _card(
                title="Thin",
                tldr=None,
                confidence="unavailable",
                summary_status="thin",
                published_at=datetime(2026, 5, 20, tzinfo=UTC),
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "2 items" in body
    assert "1 more in footer" in body


# ---------------------------------------------------------------------------
# Main-feed routing (healthy + quota carve-out only)
# ---------------------------------------------------------------------------


def test_healthy_card_renders_in_main_feed(tmp_path: Path) -> None:
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, 23, 59, 59, tzinfo=UTC),
        cards=[_card(title="The real story", tldr="The TL;DR.")],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert '<article class="card">' in body
    assert "The TL;DR." in body
    # Main feed lives inside <main>, never inside <aside id="also-seen">.
    main_block = re.search(r"<main>(.*?)</main>", body, re.DOTALL).group(1)
    assert "The real story" in main_block


def test_quota_exhausted_card_renders_in_main_feed(tmp_path: Path) -> None:
    """The ONLY non-healthy status that stays in the main feed."""
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[
            _card(
                title="Hit the cap",
                tldr=None,
                confidence="unavailable",
                summary_status="quota_exhausted",
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    main_block = re.search(r"<main>(.*?)</main>", body, re.DOTALL).group(1)
    assert '<article class="card">' in main_block
    assert "Hit the cap" in main_block
    assert QUOTA_BODY_COPY in main_block
    assert 'id="also-seen"' not in body or "Hit the cap" not in (
        re.search(r'<aside id="also-seen">(.*?)</aside>', body, re.DOTALL) or
        re.search(r"(^)", body)
    ).group(1)


def test_main_feed_body_uses_quota_copy_verbatim(tmp_path: Path) -> None:
    """The 'couldn't be generated this week' string is reserved for the
    quota carve-out; the exact wording is locked."""
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[
            _card(
                title="Quota item",
                tldr=None,
                summary_status="quota_exhausted",
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "The summary couldn't be generated this week." in body


# ---------------------------------------------------------------------------
# Footer-aside routing (everything else)
# ---------------------------------------------------------------------------


def test_thin_card_goes_to_footer_aside(tmp_path: Path) -> None:
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[
            _card(title="Healthy", tldr="real tldr"),
            _card(
                title="Too thin to summarize",
                tldr=None,
                confidence="unavailable",
                summary_status="thin",
                published_at=datetime(2026, 5, 19, tzinfo=UTC),
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    aside = re.search(r'<aside id="also-seen">(.*?)</aside>', body, re.DOTALL).group(1)
    main_block = re.search(r"<main>(.*?)</main>", body, re.DOTALL).group(1)
    assert "Too thin to summarize" in aside
    assert "Too thin to summarize" not in main_block
    assert "Also seen this week" in aside


def test_youtube_pending_local_renders_in_place_degraded(tmp_path: Path) -> None:
    """LOCKED-01 (2026-05-23 refinement): a YouTube card with a missing
    transcript renders in-place with the locked degraded body, NOT in the
    footer. Reader sees publisher + video badge + date in context."""
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[
            _card(
                title="Some video with no captions yet",
                tldr=None,
                confidence="unavailable",
                source_type="youtube",
                transcript_status="pending_local",
                summary_status="transcript_missing",
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    main_block = re.search(r"<main>(.*?)</main>", body, re.DOTALL).group(1)
    assert "Some video with no captions yet" in main_block
    assert QUOTA_BODY_COPY in main_block
    assert '<aside id="also-seen">' not in body


def test_api_error_card_renders_in_place_degraded(tmp_path: Path) -> None:
    """LOCKED-01 (2026-05-23 refinement): non-quota LLM failures
    (api_error, parse_error, client_init_error) render in-place degraded.
    Only `summary_status='thin'` routes to the footer."""
    for status in ("api_error", "parse_error", "client_init_error"):
        out = render_digest(
            week_id="2026-W21",
            week_start=datetime(2026, 5, 18, tzinfo=UTC),
            week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
            cards=[
                _card(
                    title=f"Failure {status}",
                    tldr=None,
                    summary_status=status,
                ),
            ],
            out_dir=tmp_path,
        )
        body = out.read_text(encoding="utf-8")
        main_block = re.search(r"<main>(.*?)</main>", body, re.DOTALL).group(1)
        assert f"Failure {status}" in main_block, (
            f"{status} must render in main feed (in-place degraded)"
        )
        assert QUOTA_BODY_COPY in main_block
        assert '<aside id="also-seen">' not in body, (
            f"{status} must not appear in footer aside"
        )


def test_footer_omitted_when_no_thin_items(tmp_path: Path) -> None:
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, 23, 59, 59, tzinfo=UTC),
        cards=[_card(title="Healthy", tldr="t")],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert 'id="also-seen"' not in body
    assert "Also seen this week" not in body


def test_footer_link_uses_canonical_url_with_noopener(tmp_path: Path) -> None:
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[
            _card(title="real", tldr="t"),
            _card(
                title="Thin",
                tldr=None,
                summary_status="thin",
                url="https://example.com/thin",
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    aside = re.search(r'<aside id="also-seen">(.*?)</aside>', body, re.DOTALL).group(1)
    assert 'href="https://example.com/thin"' in aside
    assert 'rel="noopener"' in aside
    assert 'target="_blank"' in aside


# ---------------------------------------------------------------------------
# D-30 video indicator (carried over)
# ---------------------------------------------------------------------------


def test_youtube_video_indicator_in_main_feed(tmp_path: Path) -> None:
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[
            _card(
                title="A YouTube card with a transcript",
                publisher="Fixture Channel",
                tldr="A real summary from the transcript.",
                source_type="youtube",
                transcript_status="ok",
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert '<span class="video-indicator">' in body
    assert VIDEO_INDICATOR in body


def test_rss_card_has_no_video_indicator(tmp_path: Path) -> None:
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[_card(title="An RSS card", tldr="t", source_type="rss")],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert '<span class="video-indicator">' not in body


# ---------------------------------------------------------------------------
# D-26 header pipeline notice (unchanged)
# ---------------------------------------------------------------------------


def test_pipeline_notice_present_when_pending(tmp_path: Path) -> None:
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[_card(title="real", tldr="t")],
        out_dir=tmp_path,
        pipeline_notice_pending_count=3,
        pipeline_notice_failed_source_count=0,
    )
    body = out.read_text(encoding="utf-8")
    assert '<p class="pipeline-notice">' in body
    assert "3 video summaries" in body


def test_pipeline_notice_absent_at_zero_state(tmp_path: Path) -> None:
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[_card(title="real", tldr="t")],
        out_dir=tmp_path,
        pipeline_notice_pending_count=0,
        pipeline_notice_failed_source_count=0,
    )
    body = out.read_text(encoding="utf-8")
    assert '<p class="pipeline-notice">' not in body


# ---------------------------------------------------------------------------
# D-24 reader-surface language policy
# ---------------------------------------------------------------------------


_FORBIDDEN_READER_TOKENS = (
    "pending_local",
    "transcript_status",
    "summary_status",
    "summary_confidence",
    "--only-pending-transcripts",
    "RESOURCE_EXHAUSTED",
    "429",
    "FetchError",
)


def test_reader_surface_avoids_engineer_tokens(tmp_path: Path) -> None:
    """No engineer-facing jargon ever lands in rendered HTML."""
    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[
            _card(title="real", tldr="t"),
            _card(
                title="thin",
                tldr=None,
                summary_status="thin",
                published_at=datetime(2026, 5, 19, tzinfo=UTC),
            ),
            _card(
                title="quota",
                tldr=None,
                summary_status="quota_exhausted",
                published_at=datetime(2026, 5, 20, tzinfo=UTC),
            ),
        ],
        out_dir=tmp_path,
        pipeline_notice_pending_count=2,
        pipeline_notice_failed_source_count=1,
    )
    body = out.read_text(encoding="utf-8")
    for token in _FORBIDDEN_READER_TOKENS:
        assert token not in body, f"reader surface leaked engineer token: {token!r}"
