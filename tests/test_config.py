"""Source registry validation tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline.config import enabled_sources, load_sources


def test_default_config_has_three_d01_sources() -> None:
    """Phase 1 ships all three D-01 RSS sources from CONTEXT.md."""
    sources = load_sources()
    assert len(sources) == 3
    ids = {s.id for s in sources}
    assert ids == {"simon-willison", "one-useful-thing", "import-ai"}

    sw = next(s for s in sources if s.id == "simon-willison")
    assert sw.type == "rss"
    assert sw.url == "https://simonwillison.net/atom/everything/"
    assert sw.enabled is True

    out = next(s for s in sources if s.id == "one-useful-thing")
    assert out.url == "https://www.oneusefulthing.org/feed"
    assert out.tag == "business"
    assert out.enabled is True

    imp = next(s for s in sources if s.id == "import-ai")
    assert imp.url == "https://importai.substack.com/feed"
    assert imp.tag == "business"
    assert imp.enabled is True


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
