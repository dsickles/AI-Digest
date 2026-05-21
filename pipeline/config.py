"""Source registry loader.

YAML is the source of truth (INGEST-01). The optional ``sources`` SQLite
table is a mirror for FK + future ETag persistence — config.py never
reads from SQLite.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

DEFAULT_SOURCES_PATH = Path("config") / "sources.yaml"

SourceType = Literal["rss"]


class SourceConfig(BaseModel):
    """One row from ``config/sources.yaml``."""

    id: str = Field(min_length=1)
    type: SourceType
    url: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    tag: str | None = None
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def _id_is_kebab(cls, value: str) -> str:
        if not all(c.isalnum() or c in "-_" for c in value):
            raise ValueError(f"source id must be kebab/snake-case ascii: {value!r}")
        return value

    @field_validator("url")
    @classmethod
    def _url_has_scheme(cls, value: str) -> str:
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError(f"source url must include http(s):// scheme: {value!r}")
        return value


class SourcesFile(BaseModel):
    sources: list[SourceConfig]


def load_sources(path: Path | str | None = None) -> list[SourceConfig]:
    """Parse and validate ``config/sources.yaml``.

    Raises ``FileNotFoundError`` if the file is missing. Pydantic raises
    ``ValidationError`` on schema violations — surfaced to the CLI.
    """
    sources_path = Path(path) if path is not None else DEFAULT_SOURCES_PATH
    if not sources_path.exists():
        raise FileNotFoundError(f"sources config not found: {sources_path}")
    raw = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    if raw is None or "sources" not in raw:
        raise ValueError(f"{sources_path} must contain a top-level 'sources:' key")
    parsed = SourcesFile.model_validate(raw)
    return parsed.sources


def enabled_sources(path: Path | str | None = None) -> list[SourceConfig]:
    """Return only sources flagged ``enabled: true`` (preserving file order)."""
    return [s for s in load_sources(path) if s.enabled]
