"""Weekly cluster ranker (PIPELINE-03).

Single Gemini call per ISO week assigns ``rank_score`` to every cluster; Python
post-processes global ``rank_position`` 1..N (D-54, D-67 stage-level checkpoint).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

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

PROMPT_VERSION = "rank_v1"
MODEL_ID = "gemini-2.5-flash"
MAX_OUTPUT_TOKENS = 4096
TEMPERATURE = 0

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "rank_v1.md"
_CLUSTERS_RE = re.compile(r"\{\{clusters_by_category\}\}")

CATEGORY_ORDER = ("edtech", "business", "technical", "design")


class RankScoreEntry(BaseModel):
    """One cluster score from structured LLM output."""

    cluster_id: str
    rank_score: float = Field(ge=0)


class RankResponse(BaseModel):
    """Structured-output contract — must match rank_v1.md."""

    rankings: list[RankScoreEntry]


class ClusterRankResult(BaseModel):
    """What the orchestrator persists into ``cluster_ranks``."""

    cluster_id: str
    rank_score: float
    rank_position: int
    rank_status: str
    prompt_version: str
    model_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd_estimate: float | None = None


@dataclass(frozen=True)
class ClusterRankInput:
    """One cluster fed to the weekly rank prompt."""

    cluster_id: str
    category: str
    title: str
    summary_text: str
    published_at: datetime


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
            "GEMINI_API_KEY is not set — add it to .env before running rank"
        )
    from google import genai

    return genai.Client(api_key=api_key)


def _format_clusters_by_category(clusters: list[ClusterRankInput]) -> str:
    """Render grouped cluster blocks for the prompt body."""
    by_category: dict[str, list[ClusterRankInput]] = {
        key: [] for key in CATEGORY_ORDER
    }
    other: list[ClusterRankInput] = []
    for cluster in clusters:
        if cluster.category in by_category:
            by_category[cluster.category].append(cluster)
        else:
            other.append(cluster)

    sections: list[str] = []
    for category in CATEGORY_ORDER:
        group = by_category[category]
        if not group:
            continue
        lines = [f"### {category}"]
        for item in group:
            summary = item.summary_text.strip() or "(no summary available)"
            lines.append(f"- cluster_id: {item.cluster_id}")
            lines.append(f"  title: {item.title}")
            lines.append(f"  summary: {summary}")
        sections.append("\n".join(lines))

    if other:
        lines = ["### uncategorized"]
        for item in other:
            summary = item.summary_text.strip() or "(no summary available)"
            lines.append(f"- cluster_id: {item.cluster_id}")
            lines.append(f"  title: {item.title}")
            lines.append(f"  summary: {summary}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def _render_user_content(clusters: list[ClusterRankInput]) -> str:
    template = _load_prompt_body()
    body = _format_clusters_by_category(clusters)
    return _CLUSTERS_RE.sub(body, template).strip()


def _assign_positions(
    clusters: list[ClusterRankInput],
    scores: dict[str, float],
    *,
    rank_status: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd_estimate: float | None = None,
) -> list[ClusterRankResult]:
    """Sort by rank_score desc, tie-break published_at then cluster_id (D-54)."""
    ordered = sorted(
        clusters,
        key=lambda c: (
            -scores.get(c.cluster_id, 0.0),
            -c.published_at.timestamp(),
            c.cluster_id,
        ),
    )
    results: list[ClusterRankResult] = []
    for position, cluster in enumerate(ordered, start=1):
        results.append(
            ClusterRankResult(
                cluster_id=cluster.cluster_id,
                rank_score=scores.get(cluster.cluster_id, 0.0),
                rank_position=position,
                rank_status=rank_status,
                prompt_version=PROMPT_VERSION,
                model_id=MODEL_ID,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd_estimate=cost_usd_estimate,
            )
        )
    return results


def _fallback_by_published_at(
    clusters: list[ClusterRankInput],
    *,
    rank_status: str,
) -> list[ClusterRankResult]:
    """D-54 / RESEARCH Focus 9: newest canonical item first on LLM failure."""
    scores = {
        c.cluster_id: c.published_at.timestamp()
        for c in clusters
    }
    return _assign_positions(
        clusters,
        scores,
        rank_status=rank_status,
    )


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
            response_schema=RankResponse,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=TEMPERATURE,
        ),
    )


def rank_week_clusters(
    *,
    week_id: str,
    clusters: list[ClusterRankInput],
    client: Any | None = None,
) -> list[ClusterRankResult]:
    """Rank every cluster in the week with one structured LLM call (D-67).

    Post-process assigns ``rank_position`` 1..N globally by ``rank_score``
    descending. On quota or API failure, falls back to ``published_at`` sort.
    """
    log = logger.bind(component="rank", week_id=week_id, cluster_count=len(clusters))
    if not clusters:
        log.info("rank.no_clusters")
        return []

    log.info("rank_start", week_id=week_id, cluster_count=len(clusters))

    try:
        active_client = client or _build_client()
    except GeminiKeyMissing:
        raise
    except Exception as exc:
        log.warning("rank.client_init_failed", error=str(exc))
        return _fallback_by_published_at(clusters, rank_status="client_init_error")

    user_content = _render_user_content(clusters)

    try:
        response = _generate(active_client, [user_content])
    except Exception as exc:
        api_status = classify_llm_exception(exc)
        log.warning(
            "rank.api_failed",
            error=type(exc).__name__,
            message=str(exc),
            rank_status=api_status,
        )
        return _fallback_by_published_at(clusters, rank_status=api_status)

    parsed: RankResponse | None = getattr(response, "parsed", None)
    if parsed is None:
        text = getattr(response, "text", "") or ""
        try:
            parsed = RankResponse.model_validate_json(text)
        except ValidationError as exc:
            log.warning("rank.parse_failed", error=str(exc), raw=text[:200])
            return _fallback_by_published_at(clusters, rank_status="parse_error")

    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    cost = _estimate_cost(input_tokens, output_tokens)

    scores = {entry.cluster_id: entry.rank_score for entry in parsed.rankings}
    missing = [c.cluster_id for c in clusters if c.cluster_id not in scores]
    if missing:
        log.warning("rank.partial_response", missing_cluster_ids=missing)
        for cluster in clusters:
            scores.setdefault(cluster.cluster_id, 0.0)

    results = _assign_positions(
        clusters,
        scores,
        rank_status="ok",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost,
    )
    log.info(
        "rank_complete",
        week_id=week_id,
        cluster_count=len(results),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=cost,
    )
    return results


__all__ = [
    "ClusterRankInput",
    "ClusterRankResult",
    "MODEL_ID",
    "PROMPT_VERSION",
    "RankResponse",
    "RankScoreEntry",
    "rank_week_clusters",
]
