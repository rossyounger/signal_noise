-- Migration: Add Hypothesis Version History
-- Stores snapshots of hypotheses prior to updates
-- Date: 2025-12-15

BEGIN;

-- ----------------------------------------------------------------------------
-- Hypothesis Versions: immutable history of hypothesis edits
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hypothesis_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    hypothesis_text TEXT NOT NULL,
    description TEXT,
    reference_url TEXT,
    reference_type TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by TEXT NOT NULL DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_hypothesis_versions_hypothesis_id_recorded_at
ON hypothesis_versions(hypothesis_id, recorded_at DESC);

-- ----------------------------------------------------------------------------
-- Trigger: snapshot prior hypothesis row on meaningful change
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trigger_snapshot_hypothesis_version()
RETURNS TRIGGER AS $$
BEGIN
    IF (
        NEW.hypothesis_text IS DISTINCT FROM OLD.hypothesis_text OR
        NEW.description IS DISTINCT FROM OLD.description OR
        NEW.reference_url IS DISTINCT FROM OLD.reference_url OR
        NEW.reference_type IS DISTINCT FROM OLD.reference_type
    ) THEN
        INSERT INTO hypothesis_versions (
            hypothesis_id,
            hypothesis_text,
            description,
            reference_url,
            reference_type,
            recorded_at,
            recorded_by
        ) VALUES (
            OLD.id,
            OLD.hypothesis_text,
            OLD.description,
            OLD.reference_url,
            OLD.reference_type,
            now(),
            'system'
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS snapshot_hypothesis_version ON hypotheses;
CREATE TRIGGER snapshot_hypothesis_version
BEFORE UPDATE ON hypotheses
FOR EACH ROW
EXECUTE FUNCTION trigger_snapshot_hypothesis_version();

COMMIT;
