"""Tier 1 title fuzzy matching via RapidFuzz (D-43, DEDUP-02)."""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

DEFAULT_THRESHOLD = 0.85


def normalize_title(text: str) -> str:
    """NFKC → lowercase → strip punctuation → collapse whitespace."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def titles_match(
    a: str,
    b: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> bool:
    """Return True when ``token_set_ratio`` meets threshold (0.85 → 85.0)."""
    left = normalize_title(a)
    right = normalize_title(b)
    if not left or not right:
        return False
    return fuzz.token_set_ratio(left, right) >= threshold * 100
