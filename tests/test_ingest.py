"""RSS adapter contract tests — fixtures, external_id, per-source isolation."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import feedparser
import pytest

from pipeline.adapters.base import FetchError
from pipeline.adapters.rss import RssAdapter, _derive_external_id
from pipeline.config import SourceConfig
from pipeline.models import NormalizedItem
from pipeline.orchestrator import RunStats, _ingest
from store.db import connect, init_db, upsert_source

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "feeds"


def _source(source_id: str, *, url: str = "https://example.com/feed") -> SourceConfig:
    return SourceConfig(
        id=source_id,
        type="rss",
        url=url,
        display_name=source_id.replace("-", " ").title(),
        tag="technical",
        enabled=True,
    )


def _fetch_fixture(name: str, monkeypatch: pytest.MonkeyPatch) -> list[NormalizedItem]:
    body = (FIXTURES / name).read_bytes()
    monkeypatch.setattr(
        "pipeline.adapters.rss._fetch_bytes",
        lambda _url: (body, 200),
    )
    return RssAdapter().fetch(_source("fixture-source", url=f"https://example.com/{name}"))


def test_rss_adapter_parses_atom_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simon Atom fixture yields a NormalizedItem with required fields."""
    items = _fetch_fixture("simon_atom.xml", monkeypatch)
    assert len(items) == 1
    item = items[0]
    assert item.title == "Fixture Atom Entry"
    assert item.canonical_url == "https://simonwillison.net/2026/May/18/test/"
    assert item.external_id == "tag:simonwillison.net,2026:/2026/May/18/test/"
    assert item.publisher == "Simon Willison's Weblog"
    assert "Hello from the Atom fixture" in item.raw_content
    assert len(item.content_hash) == 64


def test_rss_adapter_uses_guid_as_external_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Substack RSS fixture prefers stable guid over hash fallback."""
    items = _fetch_fixture("substack_rss.xml", monkeypatch)
    assert len(items) == 1
    item = items[0]
    assert item.external_id == "https://importai.substack.com/p/fixture-post"
    assert "Substack body" in item.raw_content


def test_derive_external_id_hash_fallback() -> None:
    """When guid is absent, external_id is sha256(url|published_day)."""
    entry = feedparser.parse(
        (FIXTURES / "no_guid_rss.xml").read_bytes()
    ).entries[0]
    url = "https://example.com/posts/no-guid"
    published_day = "2026-05-19"
    expected = hashlib.sha256(f"{url}|{published_day}".encode()).hexdigest()
    assert _derive_external_id(entry, url, published_day) == expected


def test_rss_adapter_treats_304_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 304 Not Modified is success with zero new items."""
    monkeypatch.setattr(
        "pipeline.adapters.rss._fetch_bytes",
        lambda _url: (b"", 304),
    )
    items = RssAdapter().fetch(_source("fixture-source"))
    assert items == []


def test_ingest_isolates_failing_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """One source raising FetchError must not prevent others from ingesting."""
    db_path = tmp_path / "aidigest-test.db"
    init_db(db_path)

    good_source = _source("good-source")
    bad_source = _source("bad-source")
    good_item = NormalizedItem.build(
        source_id="good-source",
        external_id="good-ext-1",
        canonical_url="https://example.com/good",
        title="Good Item",
        publisher="Good Source",
        published_at=datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC),
        raw_content_html="<p>ok</p>",
    )

    class GoodAdapter:
        def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
            return [good_item]

    class BadAdapter:
        def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
            raise FetchError("simulated feed failure")

    def _fake_pick(source_type: str):
        assert source_type == "rss"
        adapter = MagicMock()

        def fetch(source: SourceConfig) -> list[NormalizedItem]:
            if source.id == "bad-source":
                return BadAdapter().fetch(source)
            return GoodAdapter().fetch(source)

        adapter.fetch = fetch
        return adapter

    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", _fake_pick)

    stats = RunStats(week_id="2026-W21")
    with connect(db_path) as conn:
        for source in (good_source, bad_source):
            upsert_source(conn, source)
        conn.commit()
        items = _ingest([good_source, bad_source], conn, MagicMock(), stats)
        conn.commit()

    assert len(items) == 1
    assert items[0].external_id == "good-ext-1"
    assert len(stats.errors) == 1
    assert stats.errors[0]["source_id"] == "bad-source"
    assert stats.errors[0]["phase"] == "ingest"
