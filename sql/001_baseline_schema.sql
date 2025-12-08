-- Signal/Noise Baseline Schema
-- Generated from current Supabase database state
-- Date: 2025-12-05

BEGIN;

-- =============================================================================
-- EXTENSIONS & UTILITIES
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SOURCES: Content feed/source definitions
-- =============================================================================

CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,  -- 'rss', 'podcast', 'podcast_transcript'
    feed_url TEXT,
    ingest_config JSONB DEFAULT '{}'::JSONB,
    default_language TEXT,
    polling_interval_minutes INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER set_sources_updated_at
BEFORE UPDATE ON sources
FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- =============================================================================
-- DOCUMENTS: Ingested content artifacts
-- =============================================================================

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    external_id TEXT,
    ingest_method TEXT NOT NULL,  -- 'feed_pull', 'manual', etc.
    original_media_type TEXT,     -- 'article', 'podcast_audio', 'podcast_transcript'
    original_url TEXT,
    title TEXT,
    author TEXT,
    published_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    language TEXT,
    content_html TEXT,
    content_text TEXT,
    content_tokens INTEGER,
    transcript_status TEXT,       -- 'pending', 'completed', etc.
    transcript_source TEXT,
    assets JSONB DEFAULT '[]'::JSONB,
    ingest_status TEXT NOT NULL DEFAULT 'pending',
    ingest_error TEXT,
    provenance JSONB DEFAULT '{}'::JSONB,
    segment_status TEXT NOT NULL DEFAULT 'Not Started',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, external_id)
);

CREATE TRIGGER set_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- =============================================================================
-- SEGMENTS: Atomic content units extracted from documents
-- =============================================================================

CREATE TABLE IF NOT EXISTS segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    content_html TEXT,
    start_offset INTEGER,
    end_offset INTEGER,
    offset_kind TEXT NOT NULL DEFAULT 'text',  -- 'text', 'html', 'seconds'
    segment_status TEXT NOT NULL DEFAULT 'raw text',
    version INTEGER NOT NULL DEFAULT 1,
    labels JSONB NOT NULL DEFAULT '{}'::JSONB,
    provenance JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_segments_document_id ON segments(document_id);

CREATE TRIGGER set_segments_updated_at
BEFORE UPDATE ON segments
FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- =============================================================================
-- TRANSCRIPTION_REQUESTS: Audio transcription job queue
-- =============================================================================

CREATE TABLE IF NOT EXISTS transcription_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,       -- 'openai', 'assemblyai'
    model TEXT,
    start_seconds NUMERIC,
    end_seconds NUMERIC,
    status TEXT NOT NULL DEFAULT 'pending',
    result_text TEXT,
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER set_transcription_requests_updated_at
BEFORE UPDATE ON transcription_requests
FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- =============================================================================
-- INGESTION_REQUESTS: Source ingestion job queue
-- =============================================================================

CREATE TABLE IF NOT EXISTS ingestion_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_requests_status ON ingestion_requests(status);

CREATE TRIGGER set_ingestion_requests_updated_at
BEFORE UPDATE ON ingestion_requests
FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

-- =============================================================================
-- TOPIC_IDS: Evergreen topic identities
-- =============================================================================

CREATE TABLE IF NOT EXISTS topic_ids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- TOPICS_HISTORY: Immutable log of topic analysis per segment
-- =============================================================================

CREATE TABLE IF NOT EXISTS topics_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID NOT NULL REFERENCES topic_ids(id) ON DELETE CASCADE,
    segment_id UUID NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    user_hypothesis TEXT,
    summary_text TEXT,            -- Analysis: confirms/refutes/nuances hypothesis
    authored_by TEXT NOT NULL DEFAULT 'human',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_topics_history_topic_id ON topics_history(topic_id);
CREATE INDEX IF NOT EXISTS idx_topics_history_segment_id ON topics_history(segment_id);

-- =============================================================================
-- PERSONA_TOPIC_POVS: AI analyst point-of-view summaries
-- =============================================================================

CREATE TABLE IF NOT EXISTS persona_topic_povs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topics_history_id UUID REFERENCES topics_history(id) ON DELETE SET NULL,
    persona TEXT NOT NULL,
    pov_summary TEXT NOT NULL,
    trace_data JSONB,
    run_status TEXT NOT NULL DEFAULT 'draft',  -- 'draft', 'final'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER set_persona_topic_povs_updated_at
BEFORE UPDATE ON persona_topic_povs
FOR EACH ROW EXECUTE FUNCTION trigger_set_timestamp();

COMMIT;

