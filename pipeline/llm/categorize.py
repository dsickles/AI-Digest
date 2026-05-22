"""Per-cluster Gemini categorizer (PIPELINE-02).

Classifies each story cluster into exactly one of edtech | business | technical
| design using structured JSON output at temperature 0 (D-50).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pipeline.llm.exceptions import classify_llm_exception
from pipeline.llm.summarize import GeminiKeyMissing, _estimate_cost

logger = structlog.get_logger(__name__)

Category = Literal["edtech", "business", "technical", "design"]
VALID_CATEGORIES = frozenset({"edtech", "business", "technical", "design"})
DEFAULT_CATEGORY: Category = "technical"

PROMPT_VERSION = "categorize_v1"
MODEL_ID = "gemini-2.5-flash-lite"
MAX_OUTPUT_TOKENS = 64
TEMPERATURE = 0

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "categorize_v1.md"

_SOURCE_HINT_RE = re.compile(r"\{\{source_hint\}\}")
_TITLE_RE = re.compile(r"\{\{title\}\}")
_SUMMARY_RE = re.compile(r"\{\{summary_text\}\}")


class CategorizeResponse(BaseModel):
    """Structured-output contract — must match categorize_v1.md."""

    category: Category
    confidence: float | None = Field(default=None, ge=0, le=1)


class CategorizeResult(BaseModel):
    """What the orchestrator persists into ``cluster_summaries``."""

    category: Category
    category_confidence: str
    category_status: str
    prompt_version: str
    model_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd_estimate: float | None = None


def _load_prompt_body() -> str:
    raw = PROMPT_PATH.read_text(encoding="utf-8")
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return raw.strip()


def _build_client() -> Any:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiKeyMissing(
            "GEMINI_API_KEY is not set — add it to .env before running categorize"
        )
    from google import genai

    return genai.Client(api_key=api_key)


def _resolve_fallback_category(
    source_tag: str | None,
    *,
    last_known_category: Category | None,
) -> Category:
    if last_known_category is not None:
        return last_known_category
    if source_tag in VALID_CATEGORIES:
        return source_tag  # type: ignore[return-value]
    return DEFAULT_CATEGORY


def _format_source_hint(source_tag: str | None) -> str:
    if not source_tag:
        return ""
    return f"source_typically_covers: {source_tag}"


def _render_user_content(
    *,
    title: str,
    summary_text: str,
    source_tag: str | None,
) -> str:
    template = _load_prompt_body()
    body = summary_text.strip() or "(no summary available)"
    rendered = _TITLE_RE.sub(title, template)
    rendered = _SUMMARY_RE.sub(body, rendered)
    hint = _format_source_hint(source_tag)
    if hint:
        rendered = _SOURCE_HINT_RE.sub(hint, rendered)
    else:
        rendered = _SOURCE_HINT_RE.sub("", rendered)
    return rendered.strip()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type(Exception),
)
def _generate(client: Any, contents: list[str]) -> Any:
    from google.genai import types

    return client.models.generate_content(
        model=MODEL_ID,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CategorizeResponse,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=TEMPERATURE,
        ),
    )


def _fallback_result(
    *,
    source_tag: str | None,
    last_known_category: Category | None,
    category_confidence: str,
    category_status: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd_estimate: float | None = None,
) -> CategorizeResult:
    return CategorizeResult(
        category=_resolve_fallback_category(
            source_tag, last_known_category=last_known_category
        ),
        category_confidence=category_confidence,
        category_status=category_status,
        prompt_version=PROMPT_VERSION,
        model_id=MODEL_ID,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost_usd_estimate,
    )


def categorize_cluster(
    *,
    title: str,
    summary_text: str,
    source_tag: str | None = None,
    cluster_id: str = "",
    last_known_category: Category | None = None,
    client: Any | None = None,
) -> CategorizeResult:
    """Classify one cluster into a single category enum (D-47).

    D-49 fallbacks:
    - invalid enum / parse / api_error → source tag (or last-known) with
      ``category_confidence=fallback_source_tag``
    - quota_exhausted → same category pick with
      ``category_confidence=quota_exhausted_fallback``
    """
    log = logger.bind(component="categorize", cluster_id=cluster_id, title=title)
    if cluster_id:
        log.info("categorize_start", cluster_id=cluster_id)

    try:
        active_client = client or _build_client()
    except GeminiKeyMissing:
        raise
    except Exception as exc:
        log.warning("categorize.client_init_failed", error=str(exc))
        return _fallback_result(
            source_tag=source_tag,
            last_known_category=last_known_category,
            category_confidence="fallback_source_tag",
            category_status="client_init_error",
        )

    user_content = _render_user_content(
        title=title,
        summary_text=summary_text,
        source_tag=source_tag,
    )

    try:
        response = _generate(active_client, [user_content])
    except Exception as exc:
        api_status = classify_llm_exception(exc)
        log.warning(
            "categorize.api_failed",
            error=type(exc).__name__,
            message=str(exc),
            category_status=api_status,
        )
        if api_status == "quota_exhausted":
            return _fallback_result(
                source_tag=source_tag,
                last_known_category=last_known_category,
                category_confidence="quota_exhausted_fallback",
                category_status="quota_exhausted",
            )
        return _fallback_result(
            source_tag=source_tag,
            last_known_category=last_known_category,
            category_confidence="fallback_source_tag",
            category_status="api_error",
        )

    parsed: CategorizeResponse | None = getattr(response, "parsed", None)
    if parsed is None:
        text = getattr(response, "text", "") or ""
        try:
            parsed = CategorizeResponse.model_validate_json(text)
        except ValidationError as exc:
            log.warning("categorize.parse_failed", error=str(exc), raw=text[:200])
            return _fallback_result(
                source_tag=source_tag,
                last_known_category=last_known_category,
                category_confidence="fallback_source_tag",
                category_status="parse_error",
            )

    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    cost = _estimate_cost(input_tokens, output_tokens)

    confidence_label = (
        str(parsed.confidence) if parsed.confidence is not None else "model"
    )
    log.info(
        "categorize_complete",
        cluster_id=cluster_id,
        category=parsed.category,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost,
    )
    return CategorizeResult(
        category=parsed.category,
        category_confidence=confidence_label,
        category_status="ok",
        prompt_version=PROMPT_VERSION,
        model_id=MODEL_ID,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost,
    )


__all__ = [
    "Category",
    "CategorizeResponse",
    "CategorizeResult",
    "MODEL_ID",
    "PROMPT_VERSION",
    "VALID_CATEGORIES",
    "categorize_cluster",
]
