-- Migration: Rename persona_topic_povs evidence FK to run FK
-- Aligns naming with hypothesis_segment_link_runs after link-table re-architecture
-- Date: 2025-12-15

BEGIN;

-- Rename column (if it exists) from hypothesis_evidence_id -> hypothesis_segment_link_run_id
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'persona_topic_povs'
          AND column_name = 'hypothesis_evidence_id'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'persona_topic_povs'
          AND column_name = 'hypothesis_segment_link_run_id'
    ) THEN
        ALTER TABLE persona_topic_povs
        RENAME COLUMN hypothesis_evidence_id TO hypothesis_segment_link_run_id;
    END IF;
END $$;

-- Drop any existing FK constraint on the column (name may vary)
DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT tc.constraint_name INTO constraint_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
     AND tc.table_schema = kcu.table_schema
    WHERE tc.table_name = 'persona_topic_povs'
      AND tc.constraint_type = 'FOREIGN KEY'
      AND kcu.column_name IN ('hypothesis_evidence_id', 'hypothesis_segment_link_run_id')
    LIMIT 1;

    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE persona_topic_povs DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;

-- Add FK to run table (safe to run multiple times via exception handling)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'persona_topic_povs'
          AND column_name = 'hypothesis_segment_link_run_id'
    ) THEN
        BEGIN
            ALTER TABLE persona_topic_povs
            ADD CONSTRAINT persona_topic_povs_hypothesis_segment_link_run_id_fkey
            FOREIGN KEY (hypothesis_segment_link_run_id)
            REFERENCES hypothesis_segment_link_runs(id)
            ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN
            -- constraint already exists
            NULL;
        END;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_persona_topic_povs_hypothesis_segment_link_run_id
ON persona_topic_povs(hypothesis_segment_link_run_id);

COMMIT;
