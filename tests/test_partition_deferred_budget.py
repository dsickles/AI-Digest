"""Wave 0 RED stub — LOCKED-01 routing for deferred_budget (D-B9).

Expected to FAIL until Plan 05-03 amends
``pipeline.render.partition._IN_PLACE_TRANSIENT_STATUSES`` to include
``'deferred_budget'``.

LOCKED-01 (PROJECT.md, refined 2026-05-23): the SOLE status that routes
to the ``<aside id="also-seen">`` footer is ``summary_status='thin'``
(RSS body too short to summarize). Everything else — including the new
``deferred_budget`` sentinel introduced in Phase 5 — renders in-place in
the main feed as a degraded card.

This stub pins the LOCKED-01 contract for the new sentinel BEFORE
Plan 05-03 lands the implementation so the routing amendment cannot
silently regress.
"""
from __future__ import annotations

from pipeline.render.partition import _IN_PLACE_TRANSIENT_STATUSES


def test_deferred_budget_in_in_place_transient_statuses() -> None:
    """LOCKED-01: deferred_budget renders in the main feed, not the footer."""
    assert "deferred_budget" in _IN_PLACE_TRANSIENT_STATUSES, (
        "Plan 05-03 must add 'deferred_budget' to "
        "pipeline.render.partition._IN_PLACE_TRANSIENT_STATUSES "
        "(LOCKED-01: in-place degraded card, never footer aside)"
    )


def test_thin_remains_the_only_footer_status() -> None:
    """LOCKED-01 invariant: deferred_budget is NOT 'thin'."""
    assert "thin" not in _IN_PLACE_TRANSIENT_STATUSES, (
        "LOCKED-01 invariant: 'thin' is the sole footer-aside status and "
        "must remain OUTSIDE _IN_PLACE_TRANSIENT_STATUSES"
    )
