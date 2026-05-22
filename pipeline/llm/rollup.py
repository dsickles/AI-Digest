"""Hierarchical weekly rollup — four category minis + weekly synthesis (D-55).

Per-category minis (~80–120 words) feed a weekly synthesis (~150–200 words)
that takes **only** the four mini paragraphs as input (PITFALLS #14).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import structlog
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
CATEGORY_ORDER: tuple[Category, ...] = ("edtech", "business", "technical", "design")

CATEGORY_PROMPT_VERSION = "rollup_category_v1"
WEEKLY_PROMPT_VERSION = "rollup_weekly_v1"
MODEL_ID = "gemini-2.5-flash"
TEMPERATURE = 0.3
CATEGORY_MAX_OUTPUT_TOKENS = 512
WEEKLY_MAX_OUTPUT_TOKENS = 1024

CATEGORY_PROMPT_PATH = (
    Path(__file__).resolve().parent / "prompts" / "rollup_category_v1.md"
)
WEEKLY_PROMPT_PATH = (
    Path(__file__).resolve().parent / "prompts" / "rollup_weekly_v1.md"
)

_CATEGORY_RE = re.compile(r"\{\{category\}\}")
_CLUSTERS_RE = re.compile(r"\{\{ranked_clusters\}\}")
_MINI_EDTECH_RE = re.compile(r"\{\{mini_edtech\}\}")
_MINI_BUSINESS_RE = re.compile(r"\{\{mini_business\}\}")
_MINI_TECHNICAL_RE = re.compile(r"\{\{mini_technical\}\}")
_MINI_DESIGN_RE = re.compile(r"\{\{mini_design\}\}")


@dataclass(frozen=True)
class ClusterRollupInput:
    """One ranked cluster in a category mini rollup prompt."""

    cluster_id: str
    title: str
    summary_text: str
    rank_position: int


class RollupResult:
    """What the orchestrator persists into ``weekly_rollups``."""

    __slots__ = (
        "narrative_md",
        "rollup_status",
        "prompt_version",
        "model_id",
        "input_tokens",
        "output_tokens",
        "cost_usd_estimate",
    )

    def __init__(
        self,
        *,
        narrative_md: str | None,
        rollup_status: str,
        prompt_version: str,
        model_id: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd_estimate: float | None = None,
    ) -> None:
        self.narrative_md = narrative_md
        self.rollup_status = rollup_status
        self.prompt_version = prompt_version
        self.model_id = model_id
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd_estimate = cost_usd_estimate


def scope_for_category(category: Category) -> str:
    """DB scope discriminator for a category mini rollup."""
    return f"category:{category}"


def _load_prompt_body(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return raw.strip()


def _build_client() -> Any:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiKeyMissing(
            "GEMINI_API_KEY is not set — add it to .env before running rollup"
        )
    from google import genai

    return genai.Client(api_key=api_key)


def _format_ranked_clusters(clusters: list[ClusterRollupInput]) -> str:
    ordered = sorted(clusters, key=lambda c: c.rank_position)
    lines: list[str] = []
    for cluster in ordered:
        summary = cluster.summary_text.strip() or "(no summary available)"
        lines.append(f"- rank {cluster.rank_position}: {cluster.title}")
        lines.append(f"  summary: {summary}")
    return "\n".join(lines)


def _render_category_content(*, category: Category, clusters: list[ClusterRollupInput]) -> str:
    template = _load_prompt_body(CATEGORY_PROMPT_PATH)
    body = _format_ranked_clusters(clusters)
    rendered = _CATEGORY_RE.sub(category, template)
    rendered = _CLUSTERS_RE.sub(body, rendered)
    return rendered.strip()


def _render_weekly_content(mini_paragraphs: dict[Category, str]) -> str:
    template = _load_prompt_body(WEEKLY_PROMPT_PATH)

    def _mini(category: Category) -> str:
        text = mini_paragraphs.get(category, "").strip()
        return text or "(no mini rollup available for this category)"

    rendered = _MINI_EDTECH_RE.sub(_mini("edtech"), template)
    rendered = _MINI_BUSINESS_RE.sub(_mini("business"), rendered)
    rendered = _MINI_TECHNICAL_RE.sub(_mini("technical"), rendered)
    rendered = _MINI_DESIGN_RE.sub(_mini("design"), rendered)
    return rendered.strip()


def _failure_result(
    *,
    rollup_status: str,
    prompt_version: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd_estimate: float | None = None,
) -> RollupResult:
    return RollupResult(
        narrative_md=None,
        rollup_status=rollup_status,
        prompt_version=prompt_version,
        model_id=MODEL_ID,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost_usd_estimate,
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type(Exception),
)
def _generate_prose(
    client: Any,
    contents: list[str],
    *,
    max_output_tokens: int,
) -> Any:
    from google.genai import types

    return client.models.generate_content(
        model=MODEL_ID,
        contents=contents,
        config=types.GenerateContentConfig(
            max_output_tokens=max_output_tokens,
            temperature=TEMPERATURE,
        ),
    )


def _extract_narrative(response: Any) -> str | None:
    text = getattr(response, "text", None)
    if text is None:
        return None
    stripped = text.strip()
    return stripped or None


def rollup_category(
    *,
    week_id: str,
    category: Category,
    clusters: list[ClusterRollupInput],
    client: Any | None = None,
) -> RollupResult:
    """Produce one per-category mini rollup paragraph (D-55, D-56)."""
    scope = scope_for_category(category)
    log = logger.bind(
        component="rollup_category",
        week_id=week_id,
        scope=scope,
        cluster_count=len(clusters),
    )
    if not clusters:
        log.info("rollup_category.no_clusters")
        return _failure_result(
            rollup_status="parse_error",
            prompt_version=CATEGORY_PROMPT_VERSION,
        )

    log.info("rollup_category_start")

    try:
        active_client = client or _build_client()
    except GeminiKeyMissing:
        raise
    except Exception as exc:
        log.warning("rollup_category.client_init_failed", error=str(exc))
        return _failure_result(
            rollup_status="client_init_error",
            prompt_version=CATEGORY_PROMPT_VERSION,
        )

    user_content = _render_category_content(category=category, clusters=clusters)

    try:
        response = _generate_prose(
            active_client,
            [user_content],
            max_output_tokens=CATEGORY_MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:
        api_status = classify_llm_exception(exc)
        log.warning(
            "rollup_category.api_failed",
            error=type(exc).__name__,
            message=str(exc),
            rollup_status=api_status,
        )
        return _failure_result(
            rollup_status=api_status,
            prompt_version=CATEGORY_PROMPT_VERSION,
        )

    narrative = _extract_narrative(response)
    if not narrative:
        log.warning("rollup_category.empty_response")
        return _failure_result(
            rollup_status="parse_error",
            prompt_version=CATEGORY_PROMPT_VERSION,
        )

    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    cost = _estimate_cost(input_tokens, output_tokens)

    log.info(
        "rollup_category_complete",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost,
    )
    return RollupResult(
        narrative_md=narrative,
        rollup_status="ok",
        prompt_version=CATEGORY_PROMPT_VERSION,
        model_id=MODEL_ID,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost,
    )


def rollup_weekly(
    *,
    week_id: str,
    mini_paragraphs: dict[Category, str],
    client: Any | None = None,
) -> RollupResult:
    """Synthesize weekly narrative from four category minis only (D-55)."""
    log = logger.bind(component="rollup_weekly", week_id=week_id)
    log.info("rollup_weekly_start")

    try:
        active_client = client or _build_client()
    except GeminiKeyMissing:
        raise
    except Exception as exc:
        log.warning("rollup_weekly.client_init_failed", error=str(exc))
        return _failure_result(
            rollup_status="client_init_error",
            prompt_version=WEEKLY_PROMPT_VERSION,
        )

    user_content = _render_weekly_content(mini_paragraphs)

    try:
        response = _generate_prose(
            active_client,
            [user_content],
            max_output_tokens=WEEKLY_MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:
        api_status = classify_llm_exception(exc)
        log.warning(
            "rollup_weekly.api_failed",
            error=type(exc).__name__,
            message=str(exc),
            rollup_status=api_status,
        )
        return _failure_result(
            rollup_status=api_status,
            prompt_version=WEEKLY_PROMPT_VERSION,
        )

    narrative = _extract_narrative(response)
    if not narrative:
        log.warning("rollup_weekly.empty_response")
        return _failure_result(
            rollup_status="parse_error",
            prompt_version=WEEKLY_PROMPT_VERSION,
        )

    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    cost = _estimate_cost(input_tokens, output_tokens)

    log.info(
        "rollup_weekly_complete",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost,
    )
    return RollupResult(
        narrative_md=narrative,
        rollup_status="ok",
        prompt_version=WEEKLY_PROMPT_VERSION,
        model_id=MODEL_ID,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost,
    )


__all__ = [
    "CATEGORY_ORDER",
    "CATEGORY_PROMPT_VERSION",
    "ClusterRollupInput",
    "MODEL_ID",
    "RollupResult",
    "WEEKLY_PROMPT_VERSION",
    "rollup_category",
    "rollup_weekly",
    "scope_for_category",
]
