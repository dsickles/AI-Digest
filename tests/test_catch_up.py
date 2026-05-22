"""D-23 transcript catch-up — ``run_ingest(only_pending_transcripts=True)``.

The cloud weekly run leaves YouTube items at ``transcript_status='pending_local'``
when the transcript API is blocked. A residential follow-up run picks them up
and either advances to ``ok`` (transcript fetched) or ``missing`` (captions
genuinely don't exist — confirmed from an unblocked IP).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.adapters.youtube import YoutubeAdapter, _classify_transcript_error
from pipeline.config import YoutubeSource
from pipeline.orchestrator import RunStats, _ingest, run_ingest
from store.db import connect, init_db, upsert_source

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "feeds"


def _youtube_source() -> YoutubeSource:
    return YoutubeSource(
        id="catch-up-fixture",
        type="youtube",
        channel_id="UCFIXTURE00000000000000Z",
        display_name="Catch Up Fixture",
        tag="technical",
        enabled=True,
    )


def _seed_pending_item(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    """Seed one yt:video:dQw4w9WgXcQ item at transcript_status='pending_local'."""
    body = (FIXTURES / "youtube_channel.xml").read_bytes()
    monkeypatch.setattr(
        "pipeline.adapters.youtube._fetch_bytes",
        lambda _url: (body, 200),
    )

    class IpBlocked(Exception):
        pass

    def blocked(_video_id: str) -> str:
        raise IpBlocked("cloud blocked")

    def _stub_adapter(source_type: str):
        assert source_type == "youtube"
        return YoutubeAdapter(transcript_fetcher=blocked)

    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", _stub_adapter)

    source = _youtube_source()
    init_db(db_path)
    stats = RunStats(week_id="2026-W21")
    with connect(db_path) as conn:
        upsert_source(conn, source)
        conn.commit()
        items = _ingest([source], conn, MagicMock(), stats)
        assert items[0].transcript_status == "pending_local"


def test_classify_transcripts_disabled_catch_up_flips_to_missing() -> None:
    """Catch-up mode treats TranscriptsDisabled as confirmed missing (D-23)."""

    class TranscriptsDisabled(Exception):
        pass

    assert _classify_transcript_error(TranscriptsDisabled(), catch_up=True) == "missing"


def test_classify_transcripts_disabled_cloud_stays_pending() -> None:
    """Cloud mode (default) keeps TranscriptsDisabled at pending_local."""

    class TranscriptsDisabled(Exception):
        pass

    assert _classify_transcript_error(TranscriptsDisabled()) == "pending_local"


def test_classify_network_error_catch_up_stays_pending() -> None:
    """Catch-up mode keeps network failures at pending_local for retry."""

    class IpBlocked(Exception):
        pass

    assert _classify_transcript_error(IpBlocked(), catch_up=True) == "pending_local"


def test_catch_up_ok_updates_status_and_raw_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Successful catch-up fetch flips status to ok and writes transcript."""
    db_path = tmp_path / "aidigest-test.db"
    _seed_pending_item(monkeypatch, db_path)

    monkeypatch.setattr(
        "pipeline.adapters.youtube._transcript_text",
        lambda _vid: "fresh residential transcript text",
    )

    stats = run_ingest("2026-W21", db_path=db_path, only_pending_transcripts=True)

    assert stats.items_fetched == 1
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT transcript_status, raw_content FROM items WHERE external_id = ?",
            ("yt:video:dQw4w9WgXcQ",),
        ).fetchone()
    assert row["transcript_status"] == "ok"
    assert "fresh residential transcript" in row["raw_content"]


def test_catch_up_transcripts_disabled_flips_to_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """TranscriptsDisabled in catch-up mode advances to 'missing' (D-23)."""
    db_path = tmp_path / "aidigest-test.db"
    _seed_pending_item(monkeypatch, db_path)

    class TranscriptsDisabled(Exception):
        pass

    def disabled(_video_id: str) -> str:
        raise TranscriptsDisabled("no captions")

    monkeypatch.setattr("pipeline.adapters.youtube._transcript_text", disabled)

    stats = run_ingest("2026-W21", db_path=db_path, only_pending_transcripts=True)

    assert stats.items_fetched == 1
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT transcript_status FROM items WHERE external_id = ?",
            ("yt:video:dQw4w9WgXcQ",),
        ).fetchone()
    assert row["transcript_status"] == "missing"


def test_catch_up_still_blocked_keeps_pending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If the catch-up run is still blocked, status stays pending_local."""
    db_path = tmp_path / "aidigest-test.db"
    _seed_pending_item(monkeypatch, db_path)

    class IpBlocked(Exception):
        pass

    def still_blocked(_video_id: str) -> str:
        raise IpBlocked("still blocked")

    monkeypatch.setattr("pipeline.adapters.youtube._transcript_text", still_blocked)

    stats = run_ingest("2026-W21", db_path=db_path, only_pending_transcripts=True)

    assert stats.items_fetched == 0
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT transcript_status FROM items WHERE external_id = ?",
            ("yt:video:dQw4w9WgXcQ",),
        ).fetchone()
    assert row["transcript_status"] == "pending_local"


def test_catch_up_no_pending_items_is_noop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Empty pending queue is a no-op, not an error."""
    db_path = tmp_path / "aidigest-test.db"
    init_db(db_path)
    stats = run_ingest("2026-W21", db_path=db_path, only_pending_transcripts=True)
    assert stats.items_fetched == 0
    assert stats.errors == []


def test_catch_up_skips_rss_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Catch-up never invokes RSS adapters — D-23 is YouTube-only."""
    db_path = tmp_path / "aidigest-test.db"
    init_db(db_path)

    def _explode(source_type: str):
        raise AssertionError(f"unexpected adapter dispatch for {source_type!r}")

    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", _explode)

    stats = run_ingest("2026-W21", db_path=db_path, only_pending_transcripts=True)
    assert stats.items_fetched == 0
