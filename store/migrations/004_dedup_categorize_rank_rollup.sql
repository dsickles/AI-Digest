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

CREATE TABLE IF NOT EXISTS cluster_summaries (
    cluster_summary_id   TEXT PRIMARY KEY,
    cluster_id           TEXT NOT NULL REFERENCES story_clusters(cluster_id),
    week_id              TEXT NOT NULL,
    category             TEXT NOT NULL CHECK (category IN (
        'edtech', 'business', 'technical', 'design'
    )),
    category_confidence  TEXT,
    category_status      TEXT,
    prompt_version       TEXT NOT NULL,
    model_id             TEXT NOT NULL,
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (cluster_id, week_id, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_cluster_summaries_week ON cluster_summaries(week_id);

CREATE TABLE IF NOT EXISTS cluster_ranks (
    cluster_rank_id    TEXT PRIMARY KEY,
    cluster_id         TEXT NOT NULL REFERENCES story_clusters(cluster_id),
    week_id            TEXT NOT NULL,
    rank_score         REAL NOT NULL,
    rank_position      INTEGER NOT NULL,
    rank_status        TEXT,
    prompt_version     TEXT NOT NULL,
    model_id           TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (cluster_id, week_id, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_cluster_ranks_week ON cluster_ranks(week_id);

CREATE TABLE IF NOT EXISTS weekly_rollups (
    rollup_id             TEXT PRIMARY KEY,
    week_id               TEXT NOT NULL,
    scope                 TEXT NOT NULL,
    narrative_md          TEXT,
    rollup_status         TEXT,
    prompt_version        TEXT NOT NULL,
    model_id              TEXT NOT NULL,
    input_token_count     INTEGER,
    output_token_count    INTEGER,
    cost_usd_estimate     REAL,
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (week_id, scope, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_weekly_rollups_week ON weekly_rollups(week_id);
