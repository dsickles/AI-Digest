PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id           TEXT PRIMARY KEY,
    type                TEXT NOT NULL,
    url                 TEXT NOT NULL,
    display_name        TEXT NOT NULL,
    tag                 TEXT,
    enabled             INTEGER NOT NULL DEFAULT 1,
    etag                TEXT,
    last_modified       TEXT,
    last_fetched_at     TEXT,
    last_error          TEXT,
    last_success_at     TEXT,
    last_item_at        TEXT,
    last_error_category TEXT
);

CREATE TABLE IF NOT EXISTS items (
    item_id           TEXT PRIMARY KEY,
    source_id         TEXT NOT NULL REFERENCES sources(source_id),
    external_id       TEXT NOT NULL,
    canonical_url     TEXT NOT NULL,
    title             TEXT NOT NULL,
    publisher         TEXT NOT NULL,
    published_at      TEXT NOT NULL,
    raw_content       TEXT NOT NULL DEFAULT '',
    content_hash      TEXT NOT NULL,
    ingested_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    transcript_status TEXT,
    UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_items_published_at ON items(published_at);
CREATE INDEX IF NOT EXISTS idx_items_source_id ON items(source_id);

CREATE TABLE IF NOT EXISTS item_summaries (
    summary_id               TEXT PRIMARY KEY,
    item_id                  TEXT NOT NULL REFERENCES items(item_id),
    week_id                  TEXT NOT NULL,
    tldr                     TEXT,
    summary_confidence       TEXT NOT NULL CHECK (summary_confidence IN ('high', 'low', 'unavailable')),
    prompt_version           TEXT NOT NULL,
    model_id                 TEXT NOT NULL,
    input_tokens             INTEGER,
    output_tokens            INTEGER,
    cost_usd_estimate        REAL,
    created_at               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    summary_input_truncated  INTEGER NOT NULL DEFAULT 0,
    summary_status           TEXT,
    UNIQUE (item_id, week_id, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_item_summaries_week ON item_summaries(week_id);

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

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id              TEXT PRIMARY KEY,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    week_id             TEXT NOT NULL,
    phase               TEXT NOT NULL CHECK (phase IN (
        'ingest', 'summarize', 'render', 'all',
        'dedup', 'categorize', 'rank', 'rollup'
    )),
    status              TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
    errors_json         TEXT NOT NULL DEFAULT '[]',
    items_fetched       INTEGER NOT NULL DEFAULT 0,
    summaries_written   INTEGER NOT NULL DEFAULT 0,
    items_degraded      INTEGER NOT NULL DEFAULT 0,
    cost_usd_estimate   REAL NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_week ON pipeline_runs(week_id);
