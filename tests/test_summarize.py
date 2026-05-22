"""Summarizer tests — mocked Gemini client + hermetic enrichment."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from pipeline.config import RssSource
from pipeline.content_enrich import EnrichableItem, prepare_input_text
from pipeline.llm.summarize import (
    PROMPT_VERSION,
    SummaryResponse,
    SummaryResult,
    summarize_item,
)
from pipeline.models import NormalizedItem
from store.db import (
    connect,
    get_existing_summary,
    insert_item_summary,
    upsert_item,
    upsert_source,
)

_LONG_BODY = " ".join(["word"] * 60)


def _mock_genai_response(
    *,
    summary: str | None,
    reason: str | None = None,
    input_tokens: int = 100,
    output_tokens: int = 40,
) -> MagicMock:
    response = MagicMock()
    response.parsed = SummaryResponse(summary=summary, reason=reason)
    usage = MagicMock()
    usage.prompt_token_count = input_tokens
    usage.candidates_token_count = output_tokens
    response.usage_metadata = usage
    return response


def _mock_client(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def test_thin_content_sentinel_returns_unavailable() -> None:
    """Model thin_content JSON maps to summary_confidence unavailable."""
    response = _mock_genai_response(summary=None, reason="thin_content")
    result = summarize_item(
        title="Sparse post",
        publisher="Test Pub",
        raw_content=_LONG_BODY,
        client=_mock_client(response),
    )
    assert result.tldr is None
    assert result.summary_confidence == "unavailable"
    assert result.prompt_version == PROMPT_VERSION


def test_success_summary_returns_high_confidence() -> None:
    """Successful summary with sufficient input yields high confidence."""
    response = _mock_genai_response(
        summary="Two sentences of grounded news about the release."
    )
    result = summarize_item(
        title="Full article",
        publisher="Test Pub",
        raw_content=_LONG_BODY,
        client=_mock_client(response),
    )
    assert result.tldr == "Two sentences of grounded news about the release."
    assert result.summary_confidence == "high"
    assert result.prompt_version == PROMPT_VERSION


def test_enrichment_low_confidence_when_text_still_short() -> None:
    """Enrichment triggered + final text under 500 chars → low confidence."""
    short_rss = "tiny snippet"
    enriched = " ".join(["x"] * 40)  # passes word gate, under 500 chars
    item = EnrichableItem(
        source_id="src-1",
        item_id="item-1",
        canonical_url="https://example.com/post",
        raw_content=short_rss,
    )

    with patch(
        "pipeline.llm.summarize.prepare_input_text",
        return_value=(enriched, True),
    ):
        response = _mock_genai_response(summary="Brief but honest summary here.")
        result = summarize_item(
            title="Short post",
            publisher="Test Pub",
            raw_content=short_rss,
            canonical_url=item.canonical_url,
            item_id=item.item_id,
            source_id=item.source_id,
            client=_mock_client(response),
        )

    assert result.summary_confidence == "low"
    assert result.tldr == "Brief but honest summary here."


def test_prepare_input_text_skips_fetch_when_long() -> None:
    """RSS body >= 500 chars skips HTTP fetch (D-03)."""
    long_text = "a" * 500
    item = EnrichableItem(
        source_id="src-1",
        item_id="item-1",
        canonical_url="https://example.com/long",
        raw_content=long_text,
    )
    client = httpx.Client(transport=httpx.MockTransport(lambda req: pytest.fail("no fetch")))

    text, triggered = prepare_input_text(item, client)
    client.close()

    assert text == long_text
    assert triggered is False


def test_prepare_input_text_fetch_failure_returns_snippet(
    httpx_mock,
) -> None:
    """HTTP errors log and return best-effort RSS snippet without raising."""
    snippet = "short rss body"
    httpx_mock.add_response(status_code=503)
    item = EnrichableItem(
        source_id="src-1",
        item_id="item-1",
        canonical_url="https://example.com/fail",
        raw_content=snippet,
    )

    with httpx.Client() as client:
        text, triggered = prepare_input_text(item, client)

    assert triggered is True
    assert text == snippet


def test_prepare_input_text_uses_trafilatura_extract(
    httpx_mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When fetch succeeds, trafilatura.extract supplies the input text."""
    extracted = " ".join(["extracted"] * 80)
    httpx_mock.add_response(text="<html><body>article</body></html>")

    def fake_extract(html: str, **kwargs: object) -> str:
        assert "article" in html
        return extracted

    monkeypatch.setattr("pipeline.content_enrich.trafilatura.extract", fake_extract)
    item = EnrichableItem(
        source_id="src-1",
        item_id="item-1",
        canonical_url="https://example.com/article",
        raw_content="tiny",
    )

    with httpx.Client() as client:
        text, triggered = prepare_input_text(item, client)

    assert triggered is True
    assert text == extracted


def test_thin_content_persisted_with_unavailable_confidence(apply_schema) -> None:
    """DB row stores summary_confidence unavailable for thin_content sentinel."""
    source = RssSource(
        id="test-source",
        type="rss",
        url="https://example.com/feed",
        display_name="Test Source",
        tag="technical",
        enabled=True,
    )
    item = NormalizedItem.build(
        source_id="test-source",
        external_id="ext-thin",
        canonical_url="https://example.com/thin",
        title="Thin Item",
        publisher="Test Source",
        published_at=datetime(2026, 5, 18, tzinfo=UTC),
        raw_content_html=f"<p>{_LONG_BODY}</p>",
    )
    week_id = "2026-W20"

    with connect(apply_schema) as conn:
        upsert_source(conn, source)
        item_id = upsert_item(conn, item)
        conn.commit()

    response = _mock_genai_response(summary=None, reason="thin_content")
    result = summarize_item(
        title=item.title,
        publisher=item.publisher,
        raw_content=item.raw_content,
        client=_mock_client(response),
    )
    assert isinstance(result, SummaryResult)

    with connect(apply_schema) as conn:
        insert_item_summary(
            conn,
            item_id=item_id,
            week_id=week_id,
            tldr=result.tldr,
            summary_confidence=result.summary_confidence,
            prompt_version=result.prompt_version,
            model_id=result.model_id,
        )
        conn.commit()
        row = get_existing_summary(conn, item_id, week_id, PROMPT_VERSION)

    assert row is not None
    assert row["tldr"] is None
    assert row["summary_confidence"] == "unavailable"
    assert row["prompt_version"] == "summarize_v1"
