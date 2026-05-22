"""End-to-end renderer regression tests — store → orchestrator → HTML.

Catches the class of bugs where ``DigestCard`` defaults (e.g. ``source_type="rss"``)
silently mask real-world rendering issues because unit tests instantiate the
card directly instead of going through the full pipeline.

Plan 02-03 unit tests in ``test_render.py`` cover the renderer in isolation;
this file covers the orchestrator card-assembly path that connects the store
schema, ``_build_card_from_row``, and ``render_digest``.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pipeline.config import YoutubeSource
from pipeline.models import NormalizedItem
from pipeline.orchestrator import _build_cards_from_db
from pipeline.render.html import render_digest
from store.db import (
    connect,
    get_items_for_week,
    init_db,
    upsert_item,
    upsert_source,
)


def _youtube_item(
    *, source_id: str, external_id: str, title: str, days_ago: int = 0
) -> NormalizedItem:
    published = datetime(2026, 5, 22 - days_ago, 12, 0, tzinfo=UTC)
    return NormalizedItem.build(
        source_id=source_id,
        external_id=external_id,
        title=title,
        publisher="Fixture Channel",
        canonical_url=f"https://www.youtube.com/watch?v={external_id.split(':')[-1]}",
        published_at=published,
        raw_content_html="A fake transcript that is long enough to be a real summary input " * 5,
        transcript_status="ok",
    )


def test_youtube_card_renders_video_indicator(tmp_path: Path) -> None:
    """End-to-end: a YouTube row from SQLite renders with the [video] indicator.

    Regression for the bug shipped in Phase 2 where ``get_items_for_week`` did
    not JOIN ``sources.type``, so ``_source_type_for`` defaulted to ``rss``
    and the renderer never emitted the ``<span class="video-indicator">``
    element even though all the test fixtures had passed.
    """
    db_path = tmp_path / "aidigest-test.db"
    init_db(db_path)

    source = YoutubeSource(
        id="fixture-channel",
        type="youtube",
        channel_id="UCFIXTURE00000000000000Z",
        display_name="Fixture Channel",
        tag="technical",
        enabled=True,
    )
    item = _youtube_item(
        source_id=source.id,
        external_id="yt:video:dQw4w9WgXcQ",
        title="A YouTube card with a real transcript",
    )

    with connect(db_path) as conn:
        upsert_source(conn, source)
        upsert_item(conn, item, transcript_status="ok")
        conn.commit()

        rows = get_items_for_week(
            conn,
            "2026-05-18T00:00:00Z",
            "2026-05-24T23:59:59Z",
        )
        assert len(rows) == 1
        assert rows[0]["source_type"] == "youtube"

        cards = _build_cards_from_db(conn, rows, week_id="2026-W21")

    assert len(cards) == 1
    assert cards[0].source_type == "youtube"
    # E2E path with no summarize_v1 row infers summary_status=thin which
    # would route to the footer — to verify the video indicator we need
    # the card in the main feed, so swap in a synthetic tldr to mark it
    # healthy (matches the eventual summarize-pass state for the row).
    cards = [
        type(cards[0])(
            title=cards[0].title,
            publisher=cards[0].publisher,
            canonical_url=cards[0].canonical_url,
            published_at=cards[0].published_at,
            tldr="A real summary for the visible card",
            summary_confidence="high",
            source_type=cards[0].source_type,
            transcript_status=cards[0].transcript_status,
            summary_status="ok",
        )
    ]

    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    html = out.read_text(encoding="utf-8")

    assert '<span class="video-indicator">' in html
    assert "[video]" in html


def test_rss_card_does_not_render_video_indicator(tmp_path: Path) -> None:
    """RSS rows must not emit the video indicator (negative case)."""
    from pipeline.config import RssSource

    db_path = tmp_path / "aidigest-test.db"
    init_db(db_path)

    source = RssSource(
        id="fixture-rss",
        type="rss",
        url="https://example.com/feed.xml",
        display_name="Fixture RSS",
        tag="technical",
        enabled=True,
    )
    item = NormalizedItem.build(
        source_id=source.id,
        external_id="rss:guid:abc123",
        title="An RSS card",
        publisher="Fixture RSS",
        canonical_url="https://example.com/post",
        published_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
        raw_content_html="A real RSS body. " * 20,
    )

    with connect(db_path) as conn:
        upsert_source(conn, source)
        upsert_item(conn, item)
        conn.commit()

        rows = get_items_for_week(
            conn,
            "2026-05-18T00:00:00Z",
            "2026-05-24T23:59:59Z",
        )
        assert rows[0]["source_type"] == "rss"

        cards = _build_cards_from_db(conn, rows, week_id="2026-W21")

    # Same trick as above: ensure the card lands in the main feed for the
    # negative assertion. (Without a summarize_v1 row the orchestrator
    # infers summary_status=thin which would footer-bound the card.)
    cards = [
        type(cards[0])(
            title=cards[0].title,
            publisher=cards[0].publisher,
            canonical_url=cards[0].canonical_url,
            published_at=cards[0].published_at,
            tldr="A real RSS summary",
            summary_confidence="high",
            source_type=cards[0].source_type,
            transcript_status=cards[0].transcript_status,
            summary_status="ok",
        )
    ]

    out = render_digest(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
    )
    html = out.read_text(encoding="utf-8")

    assert '<span class="video-indicator">' not in html
    assert "[video]" not in html
