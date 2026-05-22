"""Shared fixtures for dedup unit tests."""
from __future__ import annotations

import pytest

# Positive pair: token_set_ratio >= 85 at threshold 0.85 (RESEARCH fixture).
MATCHING_TITLE_A = "Breaking: OpenAI launches GPT-5 with 2M context"
MATCHING_TITLE_B = "OpenAI launches GPT-5 with 2M context window"

# Distinct titles: score below 84 at threshold 0.84.
DISTINCT_TITLE_A = "Weekly AI roundup for enterprise buyers"
DISTINCT_TITLE_B = "How to fine-tune Llama on a laptop"


@pytest.fixture
def url_collision_pair() -> tuple[str, str]:
    """Two URLs that canonicalize to the same string (UTM vs clean)."""
    return (
        "https://www.Example.com/post?utm_source=twitter&utm_medium=social",
        "https://example.com/post",
    )


@pytest.fixture
def title_boundary_pair() -> tuple[tuple[str, str], tuple[str, str]]:
    """(match_at_0.85, no_match_at_0.84) title pairs."""
    return (
        (MATCHING_TITLE_A, MATCHING_TITLE_B),
        (DISTINCT_TITLE_A, DISTINCT_TITLE_B),
    )
