"""RSS adapter contract tests — fixtures, external_id, per-source isolation."""
from __future__ import annotations

import hashlib
from pathlib import Path

import feedparser
import pytest

from pipeline.adapters.rss import RssAdapter, _derive_external_id
from pipeline.config import SourceConfig
from pipeline.models import NormalizedItem

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
        lambda _url: body,
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
