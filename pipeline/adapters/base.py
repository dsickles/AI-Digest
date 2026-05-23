"""Adapter contract.

Every source type (rss, youtube, reddit, ...) implements ``IngestAdapter``.
Plan 01-02 grows the registry to all three Phase-1 RSS sources; Phase 2
plugs in non-RSS adapters without touching ``store/`` or ``orchestrator``.
"""
from __future__ import annotations

import re
from typing import Literal, Protocol, runtime_checkable
from urllib.parse import urlparse

from pipeline.config import SourceConfig
from pipeline.models import NormalizedItem

# UAT-FOLLOWUP-01 (Phase 3 gap-closure): YouTube Shorts must be skipped at
# ingest. They never reach summarize/categorize/rank/rollup and never appear
# in the digest footer. Match `youtube.com/shorts/<id>` and `youtu.be/shorts/`
# variants on the host+path so a stray substring elsewhere can't false-trip.
_YOUTUBE_HOSTS = frozenset({"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"})
_SHORTS_PATH_RE = re.compile(r"^/shorts(?:/|$)", re.IGNORECASE)


def is_youtube_short(url: str | None) -> bool:
    """Return True when ``url`` points at a YouTube Shorts video."""
    if not url:
        return False
    try:
        parsed = urlparse(url.strip())
    except (ValueError, AttributeError):
        return False
    host = (parsed.netloc or "").lower()
    if host not in _YOUTUBE_HOSTS:
        return False
    return bool(_SHORTS_PATH_RE.match(parsed.path or ""))

# D-39: typed error taxonomy for RunStats.errors and last_run.md.
# Categories are deliberately closed so Phase 3 pipeline_report.json (OBS-02),
# Phase 4 Pipeline-notes UI (OBS-01), and Phase 5 heartbeat (OBS-03) can layer
# downstream consumers without re-deriving these values from raw messages.
IngestErrorCategory = Literal[
    "fetch_timeout",
    "fetch_http_error",
    "parse_error",
    "empty_feed",
    "adapter_internal",
]

INGEST_ERROR_CATEGORIES: tuple[IngestErrorCategory, ...] = (
    "fetch_timeout",
    "fetch_http_error",
    "parse_error",
    "empty_feed",
    "adapter_internal",
)


class FetchError(Exception):
    """Raised by an adapter when a fetch fails non-recoverably.

    Caller (orchestrator) catches per-source so one failed feed cannot
    break the weekly run (PROJECT.md per-source isolation). The optional
    ``category`` attribute lets adapters communicate the D-39 taxonomy
    without the orchestrator parsing exception strings; ``http_status`` is
    populated when the failure originated from an HTTP response.
    """

    def __init__(
        self,
        message: str,
        *,
        category: IngestErrorCategory = "fetch_http_error",
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.category: IngestErrorCategory = category
        self.http_status: int | None = http_status


@runtime_checkable
class IngestAdapter(Protocol):
    """Stateless source fetcher."""

    def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
        """Return all parseable entries for ``source`` (caller filters by week)."""
        ...
