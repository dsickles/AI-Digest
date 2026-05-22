"""Per-item Gemini summarizer (PIPELINE-01).

Standard sync API — Batch is paid-only and skeleton stays free-tier.
tenacity wraps the call to retry 429/5xx; Pydantic schema enforces
the structured-output contract from summarize_v1.md.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pipeline.content_enrich import EnrichableItem, prepare_input_text
from pipeline.llm.exceptions import classify_llm_exception

logger = structlog.get_logger(__name__)

PROMPT_VERSION = "summarize_v1"
MODEL_ID = "gemini-2.5-flash-lite"
MAX_OUTPUT_TOKENS = 256
TEMPERATURE = 0.2

# D-28: transcript truncation policy. ~6K tokens budget at ~4 chars/token
# yields ~24K chars. When tripped we keep the first ~16K + last ~4K plus an
# explicit elision sentinel so the model does not fabricate the middle.
TRANSCRIPT_INPUT_CHAR_CAP = 24_000
TRANSCRIPT_HEAD_CHARS = 16_000
TRANSCRIPT_TAIL_CHARS = 4_000
TRANSCRIPT_ELISION_SENTINEL = "\n\n[... middle content omitted for length ...]\n\n"

# RESEARCH §2: paid Standard tier list price for cost_usd_estimate logging
INPUT_COST_PER_M_TOKENS = 0.10
OUTPUT_COST_PER_M_TOKENS = 0.40

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "summarize_v1.md"


class SummaryResponse(BaseModel):
    """Structured-output contract — must match the schema in summarize_v1.md."""

    summary: str | None = Field(default=None)
    reason: str | None = Field(default=None)


class SummaryResult(BaseModel):
    """What the orchestrator persists into ``item_summaries``."""

    tldr: str | None
    summary_confidence: str
    prompt_version: str
    model_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd_estimate: float | None = None
    summary_input_truncated: bool = False  # D-28
    # PROJECT.md LOCKED 2026-05-22: drives renderer routing (footer vs in-place).
    # 'ok' / 'thin' / 'quota_exhausted' / 'api_error' / 'parse_error' / 'client_init_error'
    summary_status: str = "ok"


def _maybe_truncate_transcript(text: str) -> tuple[str, bool]:
    """Apply D-28 elision when raw_content exceeds the transcript cap."""
    if len(text) <= TRANSCRIPT_INPUT_CHAR_CAP:
        return text, False
    head = text[:TRANSCRIPT_HEAD_CHARS].rstrip()
    tail = text[-TRANSCRIPT_TAIL_CHARS:].lstrip()
    return f"{head}{TRANSCRIPT_ELISION_SENTINEL}{tail}", True


class GeminiKeyMissing(RuntimeError):
    """Raised when GEMINI_API_KEY is not set at summarize time."""


def _load_prompt_body() -> str:
    """Strip YAML frontmatter from summarize_v1.md, return the prompt body only."""
    raw = PROMPT_PATH.read_text(encoding="utf-8")
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return raw.strip()


def _estimate_cost(input_tokens: int | None, output_tokens: int | None) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    return round(
        input_tokens * INPUT_COST_PER_M_TOKENS / 1_000_000
        + output_tokens * OUTPUT_COST_PER_M_TOKENS / 1_000_000,
        6,
    )


def _build_user_content(*, title: str, publisher: str, raw_content: str) -> str:
    """Render the per-item user message — keeps prompt + content separable."""
    body = raw_content.strip() or "(no body content available)"
    return (
        f"Title: {title}\n"
        f"Publisher: {publisher}\n"
        "---\n"
        f"{body}"
    )


def _is_thin(raw_content: str) -> bool:
    """Pre-flight thin-content gate — saves an LLM call when there's nothing to summarize."""
    return len(raw_content.strip().split()) < 30


def _build_client() -> Any:
    """Lazy import of google-genai so unit tests don't pay the SDK boot cost.

    Raises ``GeminiKeyMissing`` when the env var is absent — caller maps
    this to summary_confidence='unavailable'.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiKeyMissing(
            "GEMINI_API_KEY is not set — add it to .env or export it before running summarize"
        )
    from google import genai

    return genai.Client(api_key=api_key)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type(Exception),
)
def _generate(client: Any, contents: list[str]) -> Any:
    """One generate_content call wrapped with bounded retry (RESEARCH §2)."""
    from google.genai import types

    return client.models.generate_content(
        model=MODEL_ID,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SummaryResponse,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=TEMPERATURE,
        ),
    )


def summarize_item(
    *,
    title: str,
    publisher: str,
    raw_content: str,
    canonical_url: str = "",
    item_id: str = "",
    source_id: str = "",
    client: Any | None = None,
    httpx_client: httpx.Client | None = None,
) -> SummaryResult:
    """Generate a TL;DR for one item.

    Returns a ``SummaryResult`` with ``summary_confidence`` set to:
    - ``high``        — successful summary
    - ``low``         — model returned a non-empty summary but flagged thin_content
    - ``unavailable`` — pre-flight thin gate tripped, key missing, or
                        unrecoverable parse/API error
    """
    log = logger.bind(component="summarize", item_id=item_id, source_id=source_id, title=title)

    if item_id and source_id:
        log.info("summarize_start", item_id=item_id, source_id=source_id)

    enrichment_triggered = False
    input_text = raw_content
    if canonical_url and item_id and source_id:
        active_http = httpx_client or httpx.Client()
        try:
            input_text, enrichment_triggered = prepare_input_text(
                EnrichableItem(
                    source_id=source_id,
                    item_id=item_id,
                    canonical_url=canonical_url,
                    raw_content=raw_content,
                ),
                active_http,
            )
        finally:
            if httpx_client is None:
                active_http.close()

    # D-28: transcript truncation policy fires only for content that exceeds
    # the cap. Sets ``summary_input_truncated`` on every persisted result so
    # downstream observability (Phase 4 pipeline notes) can flag elided items.
    input_text, input_truncated = _maybe_truncate_transcript(input_text)

    if _is_thin(input_text):
        log.info(
            "summarize_complete",
            item_id=item_id,
            source_id=source_id,
            input_tokens=None,
            output_tokens=None,
            cost_usd_estimate=None,
            reason="thin_pre_check",
        )
        return SummaryResult(
            tldr=None,
            summary_confidence="unavailable",
            prompt_version=PROMPT_VERSION,
            model_id=MODEL_ID,
            summary_input_truncated=input_truncated,
            summary_status="thin",
        )

    try:
        active_client = client or _build_client()
    except GeminiKeyMissing:
        raise
    except Exception as exc:
        log.warning("summarize.client_init_failed", error=str(exc))
        return SummaryResult(
            tldr=None,
            summary_confidence="unavailable",
            prompt_version=PROMPT_VERSION,
            model_id=MODEL_ID,
            summary_input_truncated=input_truncated,
            summary_status="client_init_error",
        )

    system_prompt = _load_prompt_body()
    user_content = _build_user_content(
        title=title,
        publisher=publisher,
        raw_content=input_text,
    )

    try:
        response = _generate(active_client, [system_prompt, user_content])
    except Exception as exc:
        api_status = classify_llm_exception(exc)
        log.warning(
            "summarize.api_failed",
            error=type(exc).__name__,
            message=str(exc),
            summary_status=api_status,
        )
        return SummaryResult(
            tldr=None,
            summary_confidence="unavailable",
            prompt_version=PROMPT_VERSION,
            model_id=MODEL_ID,
            summary_input_truncated=input_truncated,
            summary_status=api_status,
        )

    parsed: SummaryResponse | None = getattr(response, "parsed", None)
    if parsed is None:
        text = getattr(response, "text", "") or ""
        try:
            parsed = SummaryResponse.model_validate_json(text)
        except Exception as exc:
            log.warning("summarize.parse_failed", error=str(exc), raw=text[:200])
            return SummaryResult(
                tldr=None,
                summary_confidence="unavailable",
                prompt_version=PROMPT_VERSION,
                model_id=MODEL_ID,
                summary_input_truncated=input_truncated,
                summary_status="parse_error",
            )

    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    cost = _estimate_cost(input_tokens, output_tokens)

    if parsed.summary and parsed.summary.strip():
        if enrichment_triggered and len(input_text.strip()) < 500:
            confidence = "low"
        else:
            confidence = "high"
        log.info(
            "summarize_complete",
            item_id=item_id,
            source_id=source_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd_estimate=cost,
            summary_confidence=confidence,
            enrichment_triggered=enrichment_triggered,
        )
        return SummaryResult(
            tldr=parsed.summary.strip(),
            summary_confidence=confidence,
            prompt_version=PROMPT_VERSION,
            model_id=MODEL_ID,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd_estimate=cost,
            summary_input_truncated=input_truncated,
            summary_status="ok",
        )

    log.info(
        "summarize_complete",
        item_id=item_id,
        source_id=source_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost,
        reason=parsed.reason,
    )
    return SummaryResult(
        tldr=None,
        summary_confidence="unavailable",
        prompt_version=PROMPT_VERSION,
        model_id=MODEL_ID,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost,
        summary_input_truncated=input_truncated,
        summary_status="thin",
    )


__all__ = [
    "MODEL_ID",
    "PROMPT_VERSION",
    "GeminiKeyMissing",
    "SummaryResponse",
    "SummaryResult",
    "summarize_item",
]
