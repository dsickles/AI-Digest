"""Source registry validation tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline.config import RssSource, YoutubeSource, enabled_sources, load_sources


def test_default_config_has_phase2_seed_sources() -> None:
    """Plan 02-01 grows the catalog to the three D-01 RSS rows + two D-29 YouTube rows.

    Plan 02-02 adds the remaining three RSS sources (D-33) to reach eight total.
    """
    sources = load_sources()
    assert len(sources) == 5
    ids = {s.id for s in sources}
    assert ids == {
        "simon-willison",
        "one-useful-thing",
        "import-ai",
        "how-i-ai",
        "nate-b-jones",
    }

    sw = next(s for s in sources if s.id == "simon-willison")
    assert isinstance(sw, RssSource)
    assert sw.type == "rss"
    assert sw.url == "https://simonwillison.net/atom/everything/"
    assert sw.enabled is True

    out = next(s for s in sources if s.id == "one-useful-thing")
    assert isinstance(out, RssSource)
    assert out.url == "https://www.oneusefulthing.org/feed"
    assert out.tag == "business"

    how = next(s for s in sources if s.id == "how-i-ai")
    assert isinstance(how, YoutubeSource)
    assert how.channel_id == "UCRYY7IEbkHLH_ScJCu9eWDQ"
    assert how.feed_url == (
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCRYY7IEbkHLH_ScJCu9eWDQ"
    )
    assert how.tag == "technical"


def test_union_loads_mixed_sources(tmp_path: Path) -> None:
    """Discriminated union accepts mixed RSS + YouTube rows in one YAML (D-36)."""
    yaml_text = """
sources:
  - id: blog-x
    type: rss
    url: https://blog.example.com/feed
    display_name: Blog X
    tag: technical
    enabled: true
  - id: chan-y
    type: youtube
    channel_id: UC0123456789ABCDEFGHIJKL
    display_name: Channel Y
    tag: business
    enabled: true
"""
    path = tmp_path / "sources.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    sources = load_sources(path)
    assert len(sources) == 2
    rss_row = next(s for s in sources if s.id == "blog-x")
    yt_row = next(s for s in sources if s.id == "chan-y")
    assert isinstance(rss_row, RssSource)
    assert isinstance(yt_row, YoutubeSource)
    assert yt_row.feed_url.endswith("channel_id=UC0123456789ABCDEFGHIJKL")


def test_invalid_channel_id_rejected(tmp_path: Path) -> None:
    """YouTube channel_id must match ^UC[A-Za-z0-9_-]{22}$ (D-36)."""
    bad = tmp_path / "sources.yaml"
    bad.write_text(
        "sources:\n"
        "  - id: bad-chan\n"
        "    type: youtube\n"
        "    channel_id: not-a-real-channel-id-1234\n"
        "    display_name: Bad\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_sources(bad)


def test_invalid_url_rejected(tmp_path: Path) -> None:
    """Schema rejects sources missing http(s):// scheme."""
    bad = tmp_path / "sources.yaml"
    bad.write_text(
        "sources:\n  - id: bad\n    type: rss\n    url: example.com/feed\n    display_name: Bad\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_sources(bad)


def test_enabled_filter(tmp_path: Path) -> None:
    """enabled_sources skips disabled rows but preserves order."""
    yaml_text = """
sources:
  - id: alpha
    type: rss
    url: https://example.com/a
    display_name: Alpha
    enabled: true
  - id: beta
    type: rss
    url: https://example.com/b
    display_name: Beta
    enabled: false
  - id: gamma
    type: rss
    url: https://example.com/c
    display_name: Gamma
    enabled: true
"""
    path = tmp_path / "sources.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    enabled = enabled_sources(path)
    assert [s.id for s in enabled] == ["alpha", "gamma"]
