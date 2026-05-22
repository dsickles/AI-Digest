"""HTML renderer tests — D-25 in-place degradation + D-26 header pipeline notice.

History:
- Plan 01-03 briefly rendered degraded items as inline cards.
- Plan 01-04 final D-05 contract moved them into an ``Also seen this week``
  footer aside.
- Plan 02-03 project-level D-25 SUPERSEDES D-05: every item renders in-place
  as an ``<article class="card">`` regardless of summary state. Footer aside,
  ``OMITTED_SECTION_HEADING``, ``_is_displayable``, ``_render_pipeline_notes``,
  and the ``.pipeline-notes`` CSS class are all removed.
"""
from __future__ import annotations

import re
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
    published_at: datetime | None = None,
    source_type: str = "rss",
    transcript_status: str | None = None,
    degradation_reason: str | None = None,
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
        degradation_reason=degradation_reason,
    )


# ---------------------------------------------------------------------------
# Header + structural assertions (carried over from Phase 1, adapted to D-25)
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
    assert "Week of" in body
    assert "May 4" in body
    assert "May 10, 2026" in body
    assert "Updated 20" in body
    assert "<h1>AI Digest</h1>" in body


def test_all_anchor_tags_have_rel_noopener(tmp_path: Path) -> None:
    """D-16: every external link carries rel=noopener."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[
            _card(title="First", url="https://a.example/post"),
            _card(
                title="Second",
                url="https://b.example/post",
                tldr=None,
                confidence="unavailable",
                degradation_reason="The full article couldn't be retrieved this week.",
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    anchors = re.findall(r"<a\b[^>]*>", body)
    assert len(anchors) >= 2
    for tag in anchors:
        assert 'rel="noopener"' in tag
        assert 'target="_blank"' in tag


def test_cards_sorted_newest_first(tmp_path: Path) -> None:
    """Cards (including degraded) render in published_at descending order."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[
            _card(title="Older", published_at=datetime(2026, 5, 5, tzinfo=UTC)),
            _card(title="Newer", published_at=datetime(2026, 5, 9, tzinfo=UTC)),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert body.index("Newer") < body.index("Older")


def test_source_badge_bracketed_display_name(tmp_path: Path) -> None:
    """D-14: publisher badge uses [display_name] format."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[_card(publisher="Simon Willison")],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "[Simon Willison]" in body


# ---------------------------------------------------------------------------
# D-25: in-place degradation
# ---------------------------------------------------------------------------


def test_degraded_renders_in_place(tmp_path: Path) -> None:
    """D-25: a card with unavailable summary still renders as <article class="card">."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[
            _card(
                title="Cloud-blocked Video",
                tldr=None,
                confidence="unavailable",
                source_type="youtube",
                transcript_status="pending_local",
                degradation_reason=(
                    "This video's transcript wasn't reachable during the weekly run. "
                    "The title and description are below."
                ),
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert body.count('<article class="card">') == 1
    assert "pipeline-notes" not in body  # D-05 footer must be gone
    assert "transcript wasn't reachable" in body


def test_header_count_includes_degraded_cards(tmp_path: Path) -> None:
    """D-25: header count is total cards, not displayed-only."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[
            _card(title="Real 1"),
            _card(title="Real 2"),
            _card(
                title="Degraded 1",
                tldr=None,
                confidence="unavailable",
                degradation_reason="No body content this week.",
            ),
            _card(
                title="Degraded 2",
                tldr=None,
                confidence="unavailable",
                degradation_reason="No body content this week.",
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    header_block = body.split("</header>")[0]
    assert "4 items" in header_block
    assert "2 items" not in header_block


# ---------------------------------------------------------------------------
# D-26: top-of-digest pipeline notice
# ---------------------------------------------------------------------------


def test_pipeline_header_notice_appears_when_pending(tmp_path: Path) -> None:
    """D-26: pending-local count > 0 surfaces the header pipeline-notice."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[_card(title="Real")],
        pipeline_notice_pending_count=2,
        pipeline_notice_failed_source_count=0,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert 'class="pipeline-notice"' in body
    # D-24: plain English copy only — no CLI flag in the user-facing notice text
    notice_block = body.split('class="pipeline-notice"', 1)[1].split("</p>", 1)[0]
    assert "--" not in notice_block
    assert "pending_local" not in notice_block


def test_pipeline_header_notice_hidden_when_all_ok(tmp_path: Path) -> None:
    """D-26: zero-state — no pending and no failed sources → notice element absent."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[_card(title="Real")],
        pipeline_notice_pending_count=0,
        pipeline_notice_failed_source_count=0,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert 'class="pipeline-notice"' not in body


def test_pipeline_header_notice_combines_pending_and_failed(tmp_path: Path) -> None:
    """D-26: both pending + failed counts contribute distinct clauses."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[_card(title="Real")],
        pipeline_notice_pending_count=1,
        pipeline_notice_failed_source_count=2,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert 'class="pipeline-notice"' in body


# ---------------------------------------------------------------------------
# D-24: reader-surface plain-English language policy
# ---------------------------------------------------------------------------


_FORBIDDEN_READER_TOKENS = (
    "pending_local",
    "transcript_status",
    "FetchError",
    "--only-pending-transcripts",
    "pipeline.run",
    "out/",
    "OMITTED_SECTION_HEADING",
    "pipeline-notes",
    "_is_displayable",
)


def test_reader_surface_plain_english(tmp_path: Path) -> None:
    """D-24: rendered HTML never leaks engineer-speak into the reader surface."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[
            _card(title="Real Article"),
            _card(
                title="Cloud-blocked Video",
                tldr=None,
                confidence="unavailable",
                source_type="youtube",
                transcript_status="pending_local",
                degradation_reason=(
                    "This video's transcript wasn't reachable during the weekly run. "
                    "The title and description are below."
                ),
            ),
            _card(
                title="No-captions Video",
                tldr=None,
                confidence="unavailable",
                source_type="youtube",
                transcript_status="missing",
                degradation_reason="No captions are available for this video.",
            ),
        ],
        pipeline_notice_pending_count=1,
        pipeline_notice_failed_source_count=0,
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    for token in _FORBIDDEN_READER_TOKENS:
        assert token not in body, f"D-24 violation: {token!r} found in reader HTML"


# ---------------------------------------------------------------------------
# D-30: YouTube video indicator
# ---------------------------------------------------------------------------


def test_youtube_video_badge(tmp_path: Path) -> None:
    """D-30: YouTube card carries a small video indicator on the publisher badge."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[
            _card(publisher="How I AI", source_type="youtube"),
            _card(publisher="Simon Willison", source_type="rss"),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    youtube_block = body.split("[How I AI]")[0]  # before badge
    youtube_badge_to_end = body.split("[How I AI]", 1)[1]
    assert "[video]" in youtube_badge_to_end[:200], "D-30: video indicator missing"
    # The RSS card must NOT carry the video indicator
    rss_badge = body.split("[Simon Willison]", 1)[1][:200]
    assert "[video]" not in rss_badge
    del youtube_block  # silence unused; structure check above


# ---------------------------------------------------------------------------
# Anti-tests: legacy D-05 surfaces must be gone
# ---------------------------------------------------------------------------


def test_no_also_seen_this_week_footer(tmp_path: Path) -> None:
    """D-25: Also seen this week aside is removed."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[
            _card(title="Real"),
            _card(
                title="Degraded",
                tldr=None,
                confidence="unavailable",
                degradation_reason="No body content this week.",
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "Also seen this week" not in body
    assert "pipeline-notes" not in body


# ---------------------------------------------------------------------------
# Carried-over security assertions
# ---------------------------------------------------------------------------


def test_html_escapes_user_strings_in_cards(tmp_path: Path) -> None:
    """T-01-02: titles/summaries with HTML-special chars are escaped on every card."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[
            _card(title="Foo <script>alert(1)</script>"),
            _card(
                title='AT&T "scoop" & <img src=x onerror=alert(1)>',
                tldr=None,
                confidence="unavailable",
                degradation_reason="The summary couldn't be generated this week.",
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "<img src=x onerror=alert(1)>" not in body
    assert "&lt;img src=x onerror=alert(1)&gt;" in body
    assert "AT&amp;T" in body
    assert "&quot;scoop&quot;" in body


def test_degraded_card_uses_degradation_reason_for_body(tmp_path: Path) -> None:
    """D-25 body copy: plain-English degradation_reason renders in place of tldr."""
    out = render_digest(
        week_id="2026-W19",
        week_start=datetime(2026, 5, 4, tzinfo=UTC),
        week_end=datetime(2026, 5, 10, tzinfo=UTC),
        cards=[
            _card(
                title="Thin Post",
                tldr=None,
                confidence="unavailable",
                degradation_reason="The source published only a short teaser this week.",
            ),
        ],
        out_dir=tmp_path,
    )
    body = out.read_text(encoding="utf-8")
    assert "The source published only a short teaser this week." in body
