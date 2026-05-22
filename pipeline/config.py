"""Source registry loader.

YAML is the source of truth (INGEST-01). The optional ``sources`` SQLite
table is a mirror for FK + future ETag persistence — config.py never
reads from SQLite.

Phase 2 D-36: ``SourceConfig`` is a Pydantic v2 discriminated union on
``type``. ``RssSource`` keeps the Phase 1 shape; ``YoutubeSource`` adds
``channel_id`` validation and derives ``feed_url`` rather than carrying
a redundant ``url`` column in the YAML.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, Field, field_validator

DEFAULT_SOURCES_PATH = Path("config") / "sources.yaml"

_KEBAB_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_YOUTUBE_FEED_TEMPLATE = (
    "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
)


_VALID_CATEGORY_TAGS = frozenset({"edtech", "business", "technical", "design"})


class _SourceBase(BaseModel):
    """Fields shared by every adapter subtype (the registry surface)."""

    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    tag: str | None = None
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def _id_is_kebab(cls, value: str) -> str:
        if not _KEBAB_RE.match(value):
            raise ValueError(f"source id must be kebab/snake-case ascii: {value!r}")
        return value

    @field_validator("tag")
    @classmethod
    def _tag_is_category_enum(cls, value: str | None) -> str | None:
        """D-49: when present, tag must be a valid categorize fallback enum."""
        if value is not None and value not in _VALID_CATEGORY_TAGS:
            raise ValueError(
                f"tag must be one of {sorted(_VALID_CATEGORY_TAGS)}: {value!r}"
            )
        return value


class RssSource(_SourceBase):
    """Phase 1 RSS/Atom feed row."""

    type: Literal["rss"]
    url: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def _url_has_scheme(cls, value: str) -> str:
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError(f"source url must include http(s):// scheme: {value!r}")
        return value


class YoutubeSource(_SourceBase):
    """Phase 2 YouTube channel row (D-27, D-29, D-36).

    The feed URL is derived from ``channel_id`` rather than stored in the
    YAML — channel RSS is the single discovery endpoint and the template is
    fixed per D-27.
    """

    type: Literal["youtube"]
    channel_id: str = Field(min_length=24, max_length=24)

    @field_validator("channel_id")
    @classmethod
    def _channel_id_shape(cls, value: str) -> str:
        if not _CHANNEL_ID_RE.match(value):
            raise ValueError(
                f"youtube channel_id must match ^UC[A-Za-z0-9_-]{{22}}$: {value!r}"
            )
        return value

    @property
    def feed_url(self) -> str:
        """Channel-uploads Atom feed URL (D-27)."""
        return _YOUTUBE_FEED_TEMPLATE.format(channel_id=self.channel_id)

    @property
    def url(self) -> str:
        """Alias for ``feed_url`` so generic callers (store/db.py) stay type-agnostic."""
        return self.feed_url


SourceConfig = Annotated[
    Union[RssSource, YoutubeSource],  # noqa: UP007 — discriminator needs explicit Union
    Field(discriminator="type"),
]


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


__all__ = [
    "RssSource",
    "SourceConfig",
    "YoutubeSource",
    "enabled_sources",
    "load_sources",
]
