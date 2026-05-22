"""Cascading invalidation planning (D-68)."""
from __future__ import annotations

from pipeline.cascade import STAGE_DEDUP, STAGE_RANK, STAGE_ROLLUP, STAGE_SUMMARIZE, plan_invalidation


def test_hash_change_on_canonical_triggers_dedup() -> None:
    stages = plan_invalidation(
        item_id="item-1",
        old_hash="abc",
        new_hash="def",
        is_canonical=True,
        title_changed=False,
        force_rebuild_clusters=False,
        force_rebuild_rollup=False,
    )
    assert STAGE_SUMMARIZE in stages
    assert STAGE_DEDUP in stages
    assert STAGE_RANK in stages
    assert STAGE_ROLLUP in stages


def test_title_change_triggers_dedup() -> None:
    stages = plan_invalidation(
        item_id="item-1",
        old_hash="same",
        new_hash="same",
        is_canonical=False,
        title_changed=True,
        force_rebuild_clusters=False,
        force_rebuild_rollup=False,
    )
    assert STAGE_DEDUP in stages


def test_membership_change_may_trigger_rank() -> None:
    stages = plan_invalidation(
        item_id="item-1",
        old_hash="a",
        new_hash="a",
        is_canonical=False,
        title_changed=False,
        membership_changed=True,
        force_rebuild_clusters=False,
        force_rebuild_rollup=False,
    )
    assert STAGE_RANK in stages


def test_force_rebuild_clusters_returns_unconditional_stages() -> None:
    stages = plan_invalidation(
        item_id="item-1",
        old_hash=None,
        new_hash=None,
        is_canonical=False,
        title_changed=False,
        force_rebuild_clusters=True,
        force_rebuild_rollup=False,
    )
    assert stages == {STAGE_DEDUP, STAGE_RANK, STAGE_ROLLUP}


def test_force_rebuild_rollup_only() -> None:
    stages = plan_invalidation(
        item_id="item-1",
        old_hash="a",
        new_hash="b",
        is_canonical=False,
        title_changed=False,
        force_rebuild_clusters=False,
        force_rebuild_rollup=True,
    )
    assert STAGE_ROLLUP in stages
