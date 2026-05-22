"""Shared LLM exception taxonomy (LOCKED-01, Phase 3).

Every LLM stage maps API/client failures through :func:`classify_llm_exception`
so quota carve-outs and footer routing stay consistent across summarize,
categorize, rank, and rollup.
"""
from __future__ import annotations


def classify_llm_exception(exc: BaseException) -> str:
    """Map an LLM-call exception to a status string.

    Returns one of:
    - ``quota_exhausted`` — Gemini RESOURCE_EXHAUSTED / HTTP 429 / rate limit
    - ``api_error`` — any other API/transport failure

    ``parse_error`` and ``client_init_error`` are set by callers when JSON
    parsing or client construction fails — not by this helper.
    """
    text = f"{type(exc).__name__} {exc!s}".lower()
    if (
        "resource_exhausted" in text
        or "429" in text
        or "rate limit" in text
        or "quota" in text
    ):
        return "quota_exhausted"
    return "api_error"


__all__ = ["classify_llm_exception"]
