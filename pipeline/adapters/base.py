"""Adapter contract.

Every source type (rss, youtube, reddit, ...) implements ``IngestAdapter``.
Plan 01-02 grows the registry to all three Phase-1 RSS sources; Phase 2
plugs in non-RSS adapters without touching ``store/`` or ``orchestrator``.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from pipeline.config import SourceConfig
from pipeline.models import NormalizedItem


class FetchError(Exception):
    """Raised by an adapter when a fetch fails non-recoverably.

    Caller (orchestrator) catches per-source so one failed feed cannot
    break the weekly run (PROJECT.md per-source isolation).
    """


@runtime_checkable
class IngestAdapter(Protocol):
    """Stateless source fetcher."""

    def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
        """Return all parseable entries for ``source`` (caller filters by week)."""
        ...
