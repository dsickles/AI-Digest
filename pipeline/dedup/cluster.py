"""Story clustering engine — Tier 0 URL + Tier 1 fuzzy union-find (D-44, D-45)."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import httpx

from pipeline.dedup.title_fuzzy import normalize_title, titles_match
from pipeline.dedup.url import canonicalize_url, resolve_final_url
from pipeline.week import week_bounds
from store.db import (
    delete_clusters_for_week,
    get_items_for_week,
    insert_cluster_member,
    insert_story_cluster,
)

if TYPE_CHECKING:
    import sqlite3

    from pipeline.orchestrator import RunStats


class _UnionFind:
    def __init__(self, keys: list[str]) -> None:
        self._parent = {key: key for key in keys}

    def find(self, key: str) -> str:
        while self._parent[key] != key:
            self._parent[key] = self._parent[self._parent[key]]
            key = self._parent[key]
        return key

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self._parent[root_right] = root_left


def _pick_canonical(members: list[sqlite3.Row]) -> sqlite3.Row:
    """D-45: longest raw_content, then published_at, then item_id."""
    return sorted(
        members,
        key=lambda row: (
            -len(row["raw_content"] or ""),
            row["published_at"],
            row["item_id"],
        ),
    )[0]


def run_dedup_for_week(
    *,
    week_id: str,
    conn: sqlite3.Connection,
    log,
    stats: RunStats,
    fetch_redirects: bool = True,
) -> int:
    """Rebuild clusters for ``week_id`` deterministically (D-67 stage checkpoint)."""
    week_start, week_end = week_bounds(week_id)
    rows = get_items_for_week(
        conn,
        week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    if not rows:
        delete_clusters_for_week(conn, week_id)
        conn.commit()
        stats.clusters_created = 0
        stats.items_clustered = 0
        return 0

    item_ids = [row["item_id"] for row in rows]
    uf = _UnionFind(item_ids)

    canonical_urls: dict[str, str] = {}
    with httpx.Client(follow_redirects=True, timeout=5.0) as client:
        for row in rows:
            url = row["canonical_url"]
            if fetch_redirects:
                canonical_urls[row["item_id"]] = resolve_final_url(url, client)
            else:
                canonical_urls[row["item_id"]] = canonicalize_url(url)

    url_buckets: dict[str, list[str]] = {}
    for item_id, url in canonical_urls.items():
        url_buckets.setdefault(url, []).append(item_id)
    for members in url_buckets.values():
        if len(members) < 2:
            continue
        anchor = members[0]
        for other in members[1:]:
            uf.union(anchor, other)

    indexed = list(enumerate(rows))
    for i, left_row in indexed:
        for j in range(i + 1, len(rows)):
            right_row = rows[j]
            if uf.find(left_row["item_id"]) == uf.find(right_row["item_id"]):
                continue
            if titles_match(left_row["title"], right_row["title"]):
                uf.union(left_row["item_id"], right_row["item_id"])

    groups: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        root = uf.find(row["item_id"])
        groups.setdefault(root, []).append(row)

    delete_clusters_for_week(conn, week_id)

    clusters_created = 0
    items_clustered = 0
    for members in groups.values():
        canonical = _pick_canonical(members)
        cluster_id = uuid.uuid4().hex
        title_norm = normalize_title(canonical["title"])
        cluster_url = canonical_urls[canonical["item_id"]]
        insert_story_cluster(
            conn,
            cluster_id=cluster_id,
            week_id=week_id,
            canonical_item_id=canonical["item_id"],
            canonical_url=cluster_url,
            title_normalized=title_norm,
        )
        for member in members:
            insert_cluster_member(
                conn,
                cluster_id=cluster_id,
                item_id=member["item_id"],
                is_canonical=member["item_id"] == canonical["item_id"],
            )
        clusters_created += 1
        if len(members) > 1:
            items_clustered += len(members) - 1

    conn.commit()
    stats.clusters_created = clusters_created
    stats.items_clustered = items_clustered
    log.info(
        "dedup.complete",
        week_id=week_id,
        clusters_created=clusters_created,
        items_clustered=items_clustered,
        items_total=len(rows),
    )
    return clusters_created
