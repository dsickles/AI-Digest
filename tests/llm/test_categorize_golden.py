"""Golden-structure tests for categorize prompt outputs (mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock

from pipeline.llm.categorize import (
    VALID_CATEGORIES,
    CategorizeResponse,
    categorize_cluster,
)


def _mock_for_category(category: str) -> MagicMock:
    response = MagicMock()
    response.parsed = CategorizeResponse(category=category, confidence=0.88)
    usage = MagicMock()
    usage.prompt_token_count = 60
    usage.candidates_token_count = 12
    response.usage_metadata = usage
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def test_all_four_enum_categories_accepted() -> None:
    """Each valid enum value produces an ok status row shape."""
    for category in sorted(VALID_CATEGORIES):
        result = categorize_cluster(
            title=f"Story in {category}",
            summary_text="Grounded summary for classification.",
            source_tag=category,
            client=_mock_for_category(category),
        )
        assert result.category == category
        assert result.category_status == "ok"
        assert result.prompt_version == "categorize_v1"
        assert result.model_id == "gemini-2.5-flash-lite"
