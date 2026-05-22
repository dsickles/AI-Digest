"""Adapter contract.

Every source type (rss, youtube, reddit, ...) implements ``IngestAdapter``.
Plan 01-02 grows the registry to all three Phase-1 RSS sources; Phase 2
plugs in non-RSS adapters without touching ``store/`` or ``orchestrator``.
"""
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pipeline.config import SourceConfig
from pipeline.models import NormalizedItem

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
