"""Hybrid RSS + trafilatura input preparation (D-03).

When the RSS body is under 500 characters, fetch the canonical URL and
extract main text with trafilatura (readability-lxml as fallback). Fetch
failures are logged and the pipeline continues with the best-effort snippet.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
import structlog
import trafilatura

logger = structlog.get_logger(__name__)

MIN_CHARS_FOR_SKIP_FETCH = 500
FETCH_TIMEOUT_S = 30.0

_WHITESPACE_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class EnrichableItem:
    """Minimal item shape for ``prepare_input_text``."""

    source_id: str
    item_id: str
    canonical_url: str
    raw_content: str


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.strip())


def _strip_html(html_fragment: str) -> str:
    return _normalize(_HTML_TAG_RE.sub(" ", html_fragment))


def _readability_fallback(html_body: str) -> str:
    from readability import Document

    return _strip_html(Document(html_body).summary())


def prepare_input_text(
    item: EnrichableItem,
    httpx_client: httpx.Client,
) -> tuple[str, bool]:
    """Return (input_text, enrichment_triggered).

    Skips the HTTP fetch when the stripped RSS body is already >= 500 chars.
    On fetch/parse failure, logs structured context and returns the RSS snippet.
    """
    text = _normalize(item.raw_content or "")
    if len(text) >= MIN_CHARS_FOR_SKIP_FETCH:
        return text, False

    enrichment_triggered = True
    log = logger.bind(
        source_id=item.source_id,
        item_id=item.item_id,
        url=item.canonical_url,
    )

    try:
        response = httpx_client.get(
            item.canonical_url,
            timeout=FETCH_TIMEOUT_S,
            follow_redirects=True,
        )
        if response.status_code >= 400:
            log.warning(
                "content_enrich.fetch_failed",
                status=response.status_code,
                error_class="HTTPStatusError",
            )
            return text, enrichment_triggered
        html_body = response.text
    except httpx.TimeoutException as exc:
        log.warning(
            "content_enrich.fetch_failed",
            status=None,
            error_class=type(exc).__name__,
        )
        return text, enrichment_triggered
    except httpx.HTTPError as exc:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        log.warning(
            "content_enrich.fetch_failed",
            status=status,
            error_class=type(exc).__name__,
        )
        return text, enrichment_triggered

    extracted = trafilatura.extract(
        html_body,
        url=item.canonical_url,
        include_comments=False,
        favor_precision=True,
    )
    if extracted:
        combined = _normalize(extracted)
        if combined:
            return combined, enrichment_triggered

    try:
        fallback = _readability_fallback(html_body)
    except Exception as exc:
        log.warning(
            "content_enrich.readability_failed",
            error_class=type(exc).__name__,
        )
        return text, enrichment_triggered

    if fallback:
        return fallback, enrichment_triggered
    return text, enrichment_triggered


__all__ = ["EnrichableItem", "MIN_CHARS_FOR_SKIP_FETCH", "prepare_input_text"]
