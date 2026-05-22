"""Pipeline domain models — pydantic for validation at adapter/store boundaries."""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(raw: str) -> str:
    """Drop HTML tags + collapse whitespace.

    Adapter input is unsanitized RSS content: Atom ``content:encoded`` often
    contains nested tags, scripts disabled by feedparser, and entities. This
    is intentionally cheap (no full HTML parser) — Plan 01-03 swaps in
    ``trafilatura`` for higher-quality extraction.
    """
    if not raw:
        return ""
    no_tags = _HTML_TAG_RE.sub(" ", raw)
    return _WHITESPACE_RE.sub(" ", no_tags).strip()


def hash_content(text: str) -> str:
    """sha256 of normalized text — content_hash column on items."""
    normalized = _WHITESPACE_RE.sub(" ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class NormalizedItem(BaseModel):
    """Adapter output. One row per upstream entry, before LLM/store."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    canonical_url: str = Field(min_length=1)
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    published_at: datetime
    raw_content: str = ""
    content_hash: str = Field(min_length=64, max_length=64)
    # D-23: lifecycle ok | pending_local | missing (None for non-video sources)
    transcript_status: str | None = None

    @field_validator("published_at")
    @classmethod
    def _require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("published_at must be timezone-aware (UTC)")
        return value.astimezone(UTC)

    @field_validator("canonical_url")
    @classmethod
    def _url_has_scheme(cls, value: str) -> str:
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError(f"canonical_url must include http(s):// scheme: {value!r}")
        return value

    def published_at_iso(self) -> str:
        """Schema-friendly ISO 8601 UTC string for ``items.published_at``."""
        return self.published_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def build(
        cls,
        *,
        source_id: str,
        external_id: str,
        canonical_url: str,
        title: str,
        publisher: str,
        published_at: datetime,
        raw_content_html: str,
        transcript_status: str | None = None,
    ) -> NormalizedItem:
        """Convenience constructor that strips HTML and computes content_hash."""
        text = strip_html(raw_content_html)
        return cls(
            source_id=source_id,
            external_id=external_id,
            canonical_url=canonical_url,
            title=title.strip(),
            publisher=publisher.strip(),
            published_at=published_at,
            raw_content=text,
            content_hash=hash_content(text),
            transcript_status=transcript_status,
        )
