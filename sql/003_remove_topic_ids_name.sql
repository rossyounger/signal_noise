-- Migration: Remove name column from topic_ids table
-- topic_ids becomes a pure identity table - all metadata comes from topics_history
-- Date: 2025-12-05

BEGIN;

-- Remove the name column from topic_ids
-- This will also automatically remove the UNIQUE constraint on name
ALTER TABLE topic_ids DROP COLUMN IF EXISTS name;

COMMIT;

