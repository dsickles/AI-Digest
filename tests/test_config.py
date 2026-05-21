"""Source registry validation tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline.config import enabled_sources, load_sources


def test_default_config_has_simon_willison() -> None:
    """Walking skeleton ships exactly the simon-willison Atom feed."""
    sources = load_sources()
    ids = {s.id for s in sources}
    assert "simon-willison" in ids, f"missing simon-willison in {ids}"

    sw = next(s for s in sources if s.id == "simon-willison")
    assert sw.type == "rss"
    assert sw.url == "https://simonwillison.net/atom/everything/"
    assert sw.enabled is True


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
