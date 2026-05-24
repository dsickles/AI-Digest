"""Wave 0 RED stub — daily-retry CLI surface (REQ-OPS-01, D-B4 + D-B9).

Expected to FAIL until Plan 05-04 implements:
- ``python -m pipeline.run summarize --retry-transient-only`` CLI flag
- Orchestrator filter scoped to ``summary_status ∈ {quota_exhausted,
  api_error, client_init_error}`` — exactly the categories that
  ``pipeline.summarize._classify_llm_exception`` produces
- ``deferred_budget`` items are explicitly NOT retried (D-B9: cap-deferred
  items are abandoned for the week; the daily retry's scope is transient
  LLM failures only)
"""
from __future__ import annotations

import subprocess
import sys

import pytest


def test_summarize_retry_transient_only_flag_in_help() -> None:
    """Plan 05-04 must add ``--retry-transient-only`` to summarize --help."""
    result = subprocess.run(
        [sys.executable, "-m", "pipeline.run", "summarize", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "--retry-transient-only" in result.stdout, (
        "Plan 05-04 must add --retry-transient-only flag on pipeline.run summarize "
        "(D-B4 daily-retry CLI surface; D-22 discoverability via --help)"
    )


def test_orchestrator_exposes_retry_transient_only_entrypoint() -> None:
    """Plan 05-04 must add a callable on orchestrator that performs the
    transient-only retry pass for the active week."""
    pytest.importorskip("pipeline.orchestrator")
    from pipeline import orchestrator

    entry = getattr(orchestrator, "retry_transient_summaries", None) or getattr(
        orchestrator, "run_summarize_retry_transient", None
    )
    assert entry is not None, (
        "Plan 05-04 must add an orchestrator entry point invoked by "
        "pipeline.run summarize --retry-transient-only "
        "(scope: summary_status in {quota_exhausted, api_error, client_init_error})"
    )


def test_retry_scope_excludes_deferred_budget() -> None:
    """The retry scope MUST NOT include 'deferred_budget' — D-B9 abandons
    cap-deferred items; only transient LLM failures retry on Mon–Sat."""
    pytest.importorskip("pipeline.orchestrator")
    from pipeline import orchestrator

    scope = getattr(orchestrator, "TRANSIENT_RETRY_STATUSES", None)
    assert scope is not None, (
        "Plan 05-04 must export pipeline.orchestrator.TRANSIENT_RETRY_STATUSES "
        "(the explicit filter set used by --retry-transient-only)"
    )
    assert "deferred_budget" not in scope, (
        "deferred_budget MUST NOT appear in the daily-retry scope — D-B9 "
        "abandons cap-deferred items for the week"
    )
    assert {"quota_exhausted", "api_error", "client_init_error"} <= set(scope)
