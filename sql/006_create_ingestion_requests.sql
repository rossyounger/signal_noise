BEGIN;

CREATE TABLE IF NOT EXISTS ingestion_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued', -- queued, in_progress, completed, failed
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_requests_status ON ingestion_requests (status);

CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_ingestion_requests_updated_at
BEFORE UPDATE ON ingestion_requests
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

COMMIT;
