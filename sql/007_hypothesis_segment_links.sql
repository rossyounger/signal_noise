-- Migration: Stable Hypothesis↔Segment Links + Run History
-- Introduces hypothesis_segment_links (stable per pair) and renames hypothesis_evidence
-- to hypothesis_segment_link_runs (append-only run log).
-- Date: 2025-12-15

BEGIN;

-- ----------------------------------------------------------------------------
-- 1) Rename question_hypotheses to question_hypothesis_links (consistency)
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'question_hypotheses'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'question_hypothesis_links'
    ) THEN
        ALTER TABLE question_hypotheses RENAME TO question_hypothesis_links;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 2) Create stable link table (one row per hypothesis_id, segment_id)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hypothesis_segment_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    segment_id UUID NOT NULL REFERENCES segments(id) ON DELETE CASCADE,

    -- Latest/current analysis state for this pair
    verdict TEXT,
    analysis_text TEXT,
    authored_by TEXT NOT NULL DEFAULT 'human',

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (hypothesis_id, segment_id)
);

CREATE INDEX IF NOT EXISTS idx_hypothesis_segment_links_hypothesis_id
ON hypothesis_segment_links(hypothesis_id);

CREATE INDEX IF NOT EXISTS idx_hypothesis_segment_links_segment_id
ON hypothesis_segment_links(segment_id);

CREATE TRIGGER set_hypothesis_segment_links_updated_at
BEFORE UPDATE ON hypothesis_segment_links
FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- ----------------------------------------------------------------------------
-- 3) Rename hypothesis_evidence -> hypothesis_segment_link_runs (append-only)
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'hypothesis_evidence'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'hypothesis_segment_link_runs'
    ) THEN
        ALTER TABLE hypothesis_evidence RENAME TO hypothesis_segment_link_runs;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 4) Add link_id + snapshot columns to run log
-- ----------------------------------------------------------------------------
ALTER TABLE hypothesis_segment_link_runs
ADD COLUMN IF NOT EXISTS link_id UUID,
ADD COLUMN IF NOT EXISTS hypothesis_text_snapshot TEXT,
ADD COLUMN IF NOT EXISTS description_snapshot TEXT,
ADD COLUMN IF NOT EXISTS reference_url_snapshot TEXT,
ADD COLUMN IF NOT EXISTS reference_type_snapshot TEXT,
ADD COLUMN IF NOT EXISTS hypothesis_updated_at_snapshot TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_hypothesis_segment_link_runs_link_id
ON hypothesis_segment_link_runs(link_id);

-- ----------------------------------------------------------------------------
-- 5) Backfill: create links from existing runs
-- ----------------------------------------------------------------------------
INSERT INTO hypothesis_segment_links (hypothesis_id, segment_id, created_at, updated_at)
SELECT
    hypothesis_id,
    segment_id,
    MIN(created_at) as created_at,
    MAX(created_at) as updated_at
FROM hypothesis_segment_link_runs
GROUP BY hypothesis_id, segment_id
ON CONFLICT (hypothesis_id, segment_id) DO NOTHING;

-- Set latest analysis fields on the link from the latest run
WITH latest_run AS (
    SELECT DISTINCT ON (hypothesis_id, segment_id)
        hypothesis_id,
        segment_id,
        verdict,
        analysis_text,
        authored_by,
        created_at
    FROM hypothesis_segment_link_runs
    ORDER BY hypothesis_id, segment_id, created_at DESC
)
UPDATE hypothesis_segment_links l
SET
    verdict = lr.verdict,
    analysis_text = lr.analysis_text,
    authored_by = lr.authored_by,
    updated_at = GREATEST(l.updated_at, lr.created_at)
FROM latest_run lr
WHERE l.hypothesis_id = lr.hypothesis_id
  AND l.segment_id = lr.segment_id;

-- Backfill link_id on runs
UPDATE hypothesis_segment_link_runs r
SET link_id = l.id
FROM hypothesis_segment_links l
WHERE r.hypothesis_id = l.hypothesis_id
  AND r.segment_id = l.segment_id
  AND r.link_id IS NULL;

-- NOTE: For historical runs, we can only snapshot current hypothesis fields.
UPDATE hypothesis_segment_link_runs r
SET
    hypothesis_text_snapshot = h.hypothesis_text,
    description_snapshot = h.description,
    reference_url_snapshot = h.reference_url,
    reference_type_snapshot = h.reference_type,
    hypothesis_updated_at_snapshot = h.updated_at
FROM hypotheses h
WHERE r.hypothesis_id = h.id
  AND r.hypothesis_text_snapshot IS NULL;

-- Enforce link_id presence going forward (after backfill)
ALTER TABLE hypothesis_segment_link_runs
ALTER COLUMN link_id SET NOT NULL;

COMMIT;
