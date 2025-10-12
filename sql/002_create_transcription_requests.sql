-- Track manual and automated transcription requests for audio documents

BEGIN;

CREATE TABLE IF NOT EXISTS transcription_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT,
    start_seconds NUMERIC,
    end_seconds NUMERIC,
    status TEXT NOT NULL DEFAULT 'queued',
    result_text TEXT,
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transcription_requests_document_id
    ON transcription_requests (document_id);

CREATE INDEX IF NOT EXISTS idx_transcription_requests_status
    ON transcription_requests (status);

CREATE TRIGGER set_transcription_requests_updated_at
BEFORE UPDATE ON transcription_requests
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

COMMIT;

