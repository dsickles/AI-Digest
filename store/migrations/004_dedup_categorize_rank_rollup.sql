-- Phase 3: dedup cluster tables (DEDUP-03) + pipeline_runs phase expansion.
-- Idempotent: CREATE IF NOT EXISTS; phase CHECK rebuild handled in db.py
-- (_ensure_pipeline_runs_phases) because SQLite cannot ALTER CHECK constraints.

CREATE TABLE IF NOT EXISTS story_clusters (
    cluster_id          TEXT PRIMARY KEY,
    week_id             TEXT NOT NULL,
    canonical_item_id   TEXT NOT NULL REFERENCES items(item_id),
    canonical_url       TEXT NOT NULL,
    title_normalized    TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_story_clusters_week ON story_clusters(week_id);

CREATE TABLE IF NOT EXISTS cluster_members (
    cluster_id    TEXT NOT NULL REFERENCES story_clusters(cluster_id),
    item_id       TEXT NOT NULL REFERENCES items(item_id),
    is_canonical  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (cluster_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_cluster_members_item ON cluster_members(item_id);
