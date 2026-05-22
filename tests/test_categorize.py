"""Categorize stage unit tests — mocked Gemini client."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from pipeline.llm.categorize import (
    PROMPT_VERSION,
    CategorizeResponse,
    CategorizeResult,
    categorize_cluster,
)
from pipeline.llm.exceptions import classify_llm_exception
from store.db import (
    connect,
    get_existing_cluster_summary,
    init_db,
    insert_cluster_summary,
    insert_story_cluster,
)


def _mock_genai_response(
    *,
    category: str,
    confidence: float | None = 0.9,
    input_tokens: int = 50,
    output_tokens: int = 10,
) -> MagicMock:
    response = MagicMock()
    response.parsed = CategorizeResponse(category=category, confidence=confidence)
    usage = MagicMock()
    usage.prompt_token_count = input_tokens
    usage.candidates_token_count = output_tokens
    response.usage_metadata = usage
    return response


def _mock_client(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def test_happy_path_returns_model_category() -> None:
    response = _mock_genai_response(category="technical")
    result = categorize_cluster(
        title="New model release",
        summary_text="A major lab shipped an updated model with lower pricing.",
        source_tag="business",
        client=_mock_client(response),
    )
    assert result.category == "technical"
    assert result.category_status == "ok"
    assert result.prompt_version == PROMPT_VERSION


def test_invalid_enum_response_falls_back_to_source_tag() -> None:
    """D-49: ValidationError on bad enum → source tag fallback."""
    response = MagicMock()
    response.parsed = None
    response.text = '{"category": "invalid_cat", "confidence": 0.5}'
    usage = MagicMock()
    usage.prompt_token_count = 40
    usage.candidates_token_count = 8
    response.usage_metadata = usage

    result = categorize_cluster(
        title="Story",
        summary_text="Summary text here.",
        source_tag="business",
        client=_mock_client(response),
    )
    assert result.category == "business"
    assert result.category_confidence == "fallback_source_tag"
    assert result.category_status == "parse_error"


def test_quota_exhausted_uses_quota_fallback_confidence() -> None:
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("429 rate limit")

    result = categorize_cluster(
        title="Story",
        summary_text="Summary text.",
        source_tag="design",
        client=client,
    )
    assert result.category == "design"
    assert result.category_confidence == "quota_exhausted_fallback"
    assert result.category_status == "quota_exhausted"


def test_classify_llm_exception_quota() -> None:
    assert classify_llm_exception(RuntimeError("RESOURCE_EXHAUSTED")) == "quota_exhausted"
    assert classify_llm_exception(RuntimeError("connection reset")) == "api_error"


def test_cluster_summaries_table_after_init(apply_schema) -> None:
    with connect(apply_schema) as conn:
        conn.execute(
            "SELECT 1 FROM cluster_summaries LIMIT 0"
        )


def test_get_existing_cluster_summary_skip(apply_schema) -> None:
    week_id = "2026-W21"
    cluster_id = "cluster-1"
    with connect(apply_schema) as conn:
        conn.execute(
            """
            INSERT INTO sources (source_id, type, url, display_name)
            VALUES ('src-1', 'rss', 'https://example.com/feed', 'Test')
            """
        )
        conn.execute(
            """
            INSERT INTO items (
                item_id, source_id, external_id, canonical_url, title,
                publisher, published_at, raw_content, content_hash
            ) VALUES (
                'item-1', 'src-1', 'ext-1', 'https://example.com/a',
                'Title', 'Test', '2026-05-20T12:00:00Z', 'body', 'hash'
            )
            """
        )
        insert_story_cluster(
            conn,
            cluster_id=cluster_id,
            week_id=week_id,
            canonical_item_id="item-1",
            canonical_url="https://example.com/a",
            title_normalized="title",
        )
        insert_cluster_summary(
            conn,
            cluster_id=cluster_id,
            week_id=week_id,
            category="technical",
            category_confidence="0.9",
            category_status="ok",
            prompt_version=PROMPT_VERSION,
            model_id="gemini-2.5-flash-lite",
        )
        conn.commit()
        existing = get_existing_cluster_summary(
            conn, cluster_id, week_id, PROMPT_VERSION
        )
    assert existing is not None
    assert existing["category"] == "technical"
