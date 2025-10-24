BEGIN;

CREATE TABLE IF NOT EXISTS segment_generation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    created_by TEXT,
    options JSONB NOT NULL DEFAULT '{}'::JSONB,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_segment_generation_requests_status
    ON segment_generation_requests (status);

CREATE INDEX IF NOT EXISTS idx_segment_generation_requests_document
    ON segment_generation_requests (document_id);

CREATE TRIGGER set_segment_generation_requests_updated_at
BEFORE UPDATE ON segment_generation_requests
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

COMMIT;
