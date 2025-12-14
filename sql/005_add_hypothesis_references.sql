-- Migration: Add External Reference Support to Hypotheses
-- Enables hypotheses to link to external documents (papers, articles, books)
-- Date: 2025-12-14

BEGIN;

-- Add reference fields to hypotheses table
ALTER TABLE hypotheses 
ADD COLUMN IF NOT EXISTS reference_url TEXT,
ADD COLUMN IF NOT EXISTS reference_type TEXT CHECK (reference_type IN ('paper', 'article', 'book', 'website', NULL));

-- Create table for caching fetched reference content
CREATE TABLE IF NOT EXISTS hypothesis_reference_cache (
    hypothesis_id UUID PRIMARY KEY REFERENCES hypotheses(id) ON DELETE CASCADE,
    full_text TEXT NOT NULL,
    character_count INTEGER NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER set_hypothesis_reference_cache_updated_at
BEFORE UPDATE ON hypothesis_reference_cache
FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- Add index for cache lookups
CREATE INDEX IF NOT EXISTS idx_hypothesis_reference_cache_fetched_at 
ON hypothesis_reference_cache(fetched_at);

COMMIT;
