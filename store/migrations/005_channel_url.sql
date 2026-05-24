-- Phase 4 UAT: publisher home / channel URL surfaced on cards.
-- YouTube sources derive this from channel_id; RSS sources optionally set
-- `home_url` in sources.yaml. Stored on the sources row so renderer JOINs can
-- pass it through to each card without a per-row source lookup.
ALTER TABLE sources ADD COLUMN channel_url TEXT;
