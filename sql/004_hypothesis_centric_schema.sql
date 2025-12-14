-- Migration: Hypothesis-Centric Architecture
-- Replaces topic_ids/topics_history with hypotheses/hypothesis_evidence
-- Adds questions table for navigation/discovery
-- Date: 2025-12-14

BEGIN;

-- =============================================================================
-- STEP 1: Create new tables
-- =============================================================================

-- Hypotheses: The primary entity - testable propositions
CREATE TABLE IF NOT EXISTS hypotheses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_text TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER set_hypotheses_updated_at
BEFORE UPDATE ON hypotheses
FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- Hypothesis Evidence: Links segments to hypotheses with verdicts
CREATE TABLE IF NOT EXISTS hypothesis_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    segment_id UUID NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    verdict TEXT,  -- 'confirms', 'refutes', 'nuances', 'irrelevant', or NULL
    analysis_text TEXT,
    authored_by TEXT NOT NULL DEFAULT 'human',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hypothesis_evidence_hypothesis_id ON hypothesis_evidence(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_hypothesis_evidence_segment_id ON hypothesis_evidence(segment_id);

-- Questions: Navigation aids that can link to hypotheses
CREATE TABLE IF NOT EXISTS questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Question-Hypothesis Links: Many-to-many relationship
CREATE TABLE IF NOT EXISTS question_hypotheses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (question_id, hypothesis_id)
);

CREATE INDEX IF NOT EXISTS idx_question_hypotheses_question_id ON question_hypotheses(question_id);
CREATE INDEX IF NOT EXISTS idx_question_hypotheses_hypothesis_id ON question_hypotheses(hypothesis_id);

-- =============================================================================
-- STEP 2: Migrate data from topics_history to new structure
-- =============================================================================

-- 2a. Create hypotheses from unique (topic_id, user_hypothesis) combinations
-- We use topic_id as the hypothesis id to preserve existing references
INSERT INTO hypotheses (id, hypothesis_text, description, created_at, updated_at)
SELECT DISTINCT ON (topic_id)
    topic_id as id,
    COALESCE(user_hypothesis, name, 'Untitled Hypothesis') as hypothesis_text,
    description,
    MIN(created_at) OVER (PARTITION BY topic_id) as created_at,
    MAX(created_at) OVER (PARTITION BY topic_id) as updated_at
FROM topics_history
WHERE topic_id IS NOT NULL
ORDER BY topic_id, created_at DESC;

-- 2b. Create hypothesis_evidence records from topics_history
-- Map summary_text to analysis_text, extract verdict from summary_text if present
INSERT INTO hypothesis_evidence (id, hypothesis_id, segment_id, verdict, analysis_text, authored_by, created_at)
SELECT 
    id,
    topic_id as hypothesis_id,
    segment_id,
    CASE 
        WHEN summary_text ILIKE '%**CONFIRMS**%' THEN 'confirms'
        WHEN summary_text ILIKE '%**REFUTES**%' THEN 'refutes'
        WHEN summary_text ILIKE '%**NUANCES**%' THEN 'nuances'
        WHEN summary_text ILIKE '%**IRRELEVANT**%' THEN 'irrelevant'
        ELSE NULL
    END as verdict,
    summary_text as analysis_text,
    authored_by,
    created_at
FROM topics_history
WHERE topic_id IS NOT NULL AND segment_id IS NOT NULL;

-- 2c. Create questions from unique topic names
INSERT INTO questions (id, question_text, created_at)
SELECT 
    gen_random_uuid() as id,
    name as question_text,
    MIN(created_at) as created_at
FROM topics_history
WHERE name IS NOT NULL AND name != ''
GROUP BY name;

-- 2d. Link questions to hypotheses based on original topics_history relationships
-- For each question (name), find the hypotheses (topic_ids) that were associated with it
INSERT INTO question_hypotheses (question_id, hypothesis_id, created_at)
SELECT DISTINCT
    q.id as question_id,
    th.topic_id as hypothesis_id,
    MIN(th.created_at) as created_at
FROM topics_history th
JOIN questions q ON q.question_text = th.name
WHERE th.topic_id IS NOT NULL AND th.name IS NOT NULL AND th.name != ''
GROUP BY q.id, th.topic_id;

-- =============================================================================
-- STEP 3: Update persona_topic_povs to reference hypothesis_evidence
-- =============================================================================

-- Add new column for hypothesis_evidence reference
ALTER TABLE persona_topic_povs 
ADD COLUMN IF NOT EXISTS hypothesis_evidence_id UUID REFERENCES hypothesis_evidence(id) ON DELETE SET NULL;

-- Migrate existing references (topics_history_id maps directly to hypothesis_evidence.id)
UPDATE persona_topic_povs 
SET hypothesis_evidence_id = topics_history_id
WHERE topics_history_id IS NOT NULL;

-- =============================================================================
-- STEP 4: Drop old tables and columns
-- =============================================================================

-- Drop the old FK column from persona_topic_povs
ALTER TABLE persona_topic_povs DROP COLUMN IF EXISTS topics_history_id;

-- Drop old tables (CASCADE will handle any remaining FKs)
DROP TABLE IF EXISTS topics_history CASCADE;
DROP TABLE IF EXISTS topic_ids CASCADE;

COMMIT;
