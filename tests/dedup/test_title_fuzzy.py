"""Unit tests for Tier 1 title fuzzy matching."""
from __future__ import annotations

from pipeline.dedup.title_fuzzy import normalize_title, titles_match
from tests.dedup.conftest import (
    DISTINCT_TITLE_A,
    DISTINCT_TITLE_B,
    MATCHING_TITLE_A,
    MATCHING_TITLE_B,
)


def test_titles_match_at_default_threshold() -> None:
    assert titles_match(MATCHING_TITLE_A, MATCHING_TITLE_B) is True


def test_titles_no_match_at_084_threshold() -> None:
    assert titles_match(DISTINCT_TITLE_A, DISTINCT_TITLE_B, threshold=0.84) is False


def test_boundary_085_accepts_research_pair() -> None:
    assert titles_match(MATCHING_TITLE_A, MATCHING_TITLE_B, threshold=0.85) is True


def test_boundary_086_rejects_distinct_pair() -> None:
    assert titles_match(DISTINCT_TITLE_A, DISTINCT_TITLE_B, threshold=0.86) is False


def test_normalize_title_nfkc_and_case() -> None:
    assert normalize_title("Ｃｕｒｉｏｕｓ — AI!") == "curious ai"
