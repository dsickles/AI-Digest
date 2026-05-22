"""Cascading invalidation when item content changes (D-68).

Pure planning function — orchestrator applies returned stage names.
"""
from __future__ import annotations

STAGE_SUMMARIZE = "summarize"
STAGE_DEDUP = "dedup"
STAGE_RANK = "rank"
STAGE_ROLLUP = "rollup"


def plan_invalidation(
    *,
    item_id: str,
    old_hash: str | None,
    new_hash: str | None,
    is_canonical: bool,
    title_changed: bool,
    membership_changed: bool = False,
    top_n_composition_changed: bool = False,
    force_rebuild_clusters: bool = False,
    force_rebuild_rollup: bool = False,
) -> set[str]:
    """Return pipeline stages that must re-run after an item change.

    ``item_id`` is accepted for logging symmetry with RESEARCH; unused in
    pure planning logic.
    """
    del item_id  # reserved for future per-item audit hooks

    stages: set[str] = set()

    if force_rebuild_clusters:
        stages.update({STAGE_DEDUP, STAGE_RANK, STAGE_ROLLUP})
        return stages

    if force_rebuild_rollup:
        stages.add(STAGE_ROLLUP)
        if not membership_changed and not top_n_composition_changed:
            return stages

    hash_changed = (
        old_hash is not None
        and new_hash is not None
        and old_hash != new_hash
    )
    if not hash_changed and not title_changed and not membership_changed:
        if force_rebuild_rollup:
            return {STAGE_ROLLUP}
        return stages

    if hash_changed or title_changed:
        stages.add(STAGE_SUMMARIZE)

    if (hash_changed and is_canonical) or title_changed:
        stages.add(STAGE_DEDUP)

    if membership_changed or STAGE_DEDUP in stages:
        stages.add(STAGE_RANK)

    if top_n_composition_changed or STAGE_RANK in stages:
        stages.add(STAGE_ROLLUP)

    if force_rebuild_rollup:
        stages.add(STAGE_ROLLUP)

    return stages


__all__ = ["plan_invalidation"]
