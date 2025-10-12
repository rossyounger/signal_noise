-- FR1 baseline schema: sources and documents
-- sources stores metadata about each feed/podcast/manual source
-- documents stores the ingested parent artifacts linked back to a source

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    feed_url TEXT,
    ingest_config JSONB DEFAULT '{}'::JSONB,
    default_language TEXT,
    polling_interval_minutes INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name)
);

CREATE TRIGGER set_sources_updated_at
BEFORE UPDATE ON sources
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    external_id TEXT,
    ingest_method TEXT NOT NULL,
    original_media_type TEXT,
    original_url TEXT,
    title TEXT,
    author TEXT,
    published_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    language TEXT,
    content_html TEXT,
    content_text TEXT,
    content_tokens INTEGER,
    transcript_status TEXT,
    transcript_source TEXT,
    assets JSONB DEFAULT '[]'::JSONB,
    ingest_status TEXT NOT NULL DEFAULT 'pending',
    ingest_error TEXT,
    provenance JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, external_id)
);

CREATE TRIGGER set_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

COMMIT;

