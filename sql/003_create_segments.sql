BEGIN;

CREATE TABLE IF NOT EXISTS segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    start_offset INTEGER,
    end_offset INTEGER,
    segment_status TEXT NOT NULL DEFAULT 'proposed',
    version INTEGER NOT NULL DEFAULT 1,
    labels JSONB NOT NULL DEFAULT '{}'::JSONB,
    provenance JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_segments_document_id
    ON segments (document_id);

CREATE TRIGGER set_segments_updated_at
BEFORE UPDATE ON segments
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

COMMIT;
