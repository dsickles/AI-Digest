-- Phase 2 expand-ingestion: additive columns for YouTube + source-health (D-23, D-28, D-40).
--
-- Idempotent: the migration runner in store/db.py executes each statement
-- individually and swallows "duplicate column name" errors, so re-applying
-- this migration on an already-migrated database is a no-op.
--
-- ALTER TABLE ADD COLUMN does NOT support IF NOT EXISTS in SQLite; the
-- runner handles re-entry via OperationalError detection rather than SQL syntax.

-- D-23: YouTube transcript lifecycle on items
--   NULL          → not applicable (non-video sources)
--   'ok'          → captions fetched successfully
--   'pending_local' → cloud-blocked or transient; eligible for --only-pending-transcripts retry
--   'missing'     → no captions available on the video; never retried
ALTER TABLE items ADD COLUMN transcript_status TEXT;

-- D-28: observability for transcript-truncation policy on item_summaries.
--   0 → input fit in the LLM context window; 1 → reshaped to first + last + elision sentinel
ALTER TABLE item_summaries ADD COLUMN summary_input_truncated INTEGER NOT NULL DEFAULT 0;

-- D-40: source-health columns on sources (feed Phase 4 OBS-01 + Phase 5 heartbeat)
ALTER TABLE sources ADD COLUMN last_success_at TEXT;
ALTER TABLE sources ADD COLUMN last_item_at TEXT;
ALTER TABLE sources ADD COLUMN last_error_category TEXT;
