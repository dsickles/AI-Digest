"""Deterministic dedup-before-LLM (Tier 0 URL + Tier 1 title fuzzy)."""

from pipeline.dedup.cluster import run_dedup_for_week
from pipeline.dedup.title_fuzzy import DEFAULT_THRESHOLD, normalize_title, titles_match
from pipeline.dedup.url import canonicalize_url, resolve_final_url

__all__ = [
    "DEFAULT_THRESHOLD",
    "canonicalize_url",
    "normalize_title",
    "resolve_final_url",
    "run_dedup_for_week",
    "titles_match",
]
