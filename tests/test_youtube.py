"""YouTube adapter contract tests — channel-RSS parsing + transcript lifecycle.

Network-free: ``_fetch_bytes`` and the transcript fetcher are both monkeypatched.
Covers INGEST-03 happy path (ok), cloud-blocked (pending_local), and the
end-to-end orchestrator wiring in :func:`pipeline.orchestrator._pick_adapter`.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.adapters.youtube import YoutubeAdapter
from pipeline.config import YoutubeSource
from pipeline.orchestrator import RunStats, _ingest, _pick_adapter
from store.db import connect, init_db, upsert_source

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "feeds"


def _youtube_source(
    *,
    id: str = "fixture-channel",
    channel_id: str = "UCFIXTURE00000000000000Z",
    display_name: str = "Fixture Channel",
    tag: str | None = "technical",
) -> YoutubeSource:
    return YoutubeSource(
        id=id,
        type="youtube",
        channel_id=channel_id,
        display_name=display_name,
        tag=tag,
        enabled=True,
    )


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, body: bytes, status: int = 200) -> None:
    monkeypatch.setattr(
        "pipeline.adapters.youtube._fetch_bytes",
        lambda _url: (body, status),
    )


def test_youtube_adapter_parses_channel_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture channel RSS yields one NormalizedItem with yt:video: external_id."""
    body = (FIXTURES / "youtube_channel.xml").read_bytes()
    _patch_fetch(monkeypatch, body)
    adapter = YoutubeAdapter(transcript_fetcher=lambda _vid: "fake transcript text here")

    items = adapter.fetch(_youtube_source())

    assert len(items) == 1
    item = items[0]
    assert item.external_id == "yt:video:dQw4w9WgXcQ"
    assert item.canonical_url.startswith("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert item.publisher == "Fixture Channel"
    assert item.transcript_status == "ok"
    assert "fake transcript text" in item.raw_content


def test_transcript_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful transcript fetch produces transcript_status=ok and replaces raw_content."""
    body = (FIXTURES / "youtube_channel.xml").read_bytes()
    _patch_fetch(monkeypatch, body)

    transcript = "Hello viewers and welcome back to How I AI. " * 5
    adapter = YoutubeAdapter(transcript_fetcher=lambda _vid: transcript)
    items = adapter.fetch(_youtube_source())

    assert len(items) == 1
    assert items[0].transcript_status == "ok"
    assert transcript.strip() in items[0].raw_content


def test_transcript_ip_blocked_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """IpBlocked maps to transcript_status=pending_local (D-23)."""
    body = (FIXTURES / "youtube_channel.xml").read_bytes()
    _patch_fetch(monkeypatch, body)

    class IpBlocked(Exception):
        pass

    def raise_blocked(_video_id: str) -> str:
        raise IpBlocked("cloud IP blocked by YouTube")

    adapter = YoutubeAdapter(transcript_fetcher=raise_blocked)
    items = adapter.fetch(_youtube_source())

    assert len(items) == 1
    assert items[0].transcript_status == "pending_local"
    # Description fallback (from media:description) survives
    assert "fixture" in items[0].raw_content.lower()


def test_transcripts_disabled_on_cloud_is_pending_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cloud ingest: TranscriptsDisabled is pending_local, never missing (D-23)."""
    body = (FIXTURES / "youtube_channel.xml").read_bytes()
    _patch_fetch(monkeypatch, body)

    class TranscriptsDisabled(Exception):
        pass

    adapter = YoutubeAdapter(
        transcript_fetcher=lambda _vid: (_ for _ in ()).throw(TranscriptsDisabled("disabled"))
    )
    items = adapter.fetch(_youtube_source())

    assert len(items) == 1
    assert items[0].transcript_status == "pending_local"


def test_pick_adapter_returns_youtube_for_youtube_type() -> None:
    """Orchestrator registry dispatches on the discriminated-union subtype (D-36)."""
    adapter = _pick_adapter("youtube")
    assert isinstance(adapter, YoutubeAdapter)


def test_transcript_status_persisted_through_ingest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end: _ingest writes transcript_status into the items row."""
    body = (FIXTURES / "youtube_channel.xml").read_bytes()
    _patch_fetch(monkeypatch, body)

    def _stub_adapter(source_type: str):
        assert source_type == "youtube"
        return YoutubeAdapter(transcript_fetcher=lambda _vid: "a real transcript would go here")

    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", _stub_adapter)

    source = _youtube_source(id="how-i-ai-fixture")
    db_path = tmp_path / "aidigest-test.db"
    init_db(db_path)
    stats = RunStats(week_id="2026-W21")

    with connect(db_path) as conn:
        upsert_source(conn, source)
        conn.commit()
        items = _ingest([source], conn, MagicMock(), stats)
        row = conn.execute(
            "SELECT transcript_status, raw_content FROM items WHERE source_id = ?",
            (source.id,),
        ).fetchone()

    assert len(items) == 1
    assert items[0].transcript_status == "ok"
    assert row is not None
    assert row["transcript_status"] == "ok"


def _setup_youtube_for_classify_test(monkeypatch: pytest.MonkeyPatch) -> None:
    body = (FIXTURES / "youtube_channel.xml").read_bytes()
    _patch_fetch(monkeypatch, body)


def test_classify_named_blocked_error_pending_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """The classifier looks at the exception class name so test doubles work."""
    _setup_youtube_for_classify_test(monkeypatch)

    class RequestBlocked(Exception):
        pass

    def raise_blocked(_video_id: str) -> str:
        raise RequestBlocked("blocked")

    adapter = YoutubeAdapter(transcript_fetcher=raise_blocked)
    items = adapter.fetch(_youtube_source())
    assert items[0].transcript_status == "pending_local"
