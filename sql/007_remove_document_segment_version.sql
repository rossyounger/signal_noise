BEGIN;

ALTER TABLE documents
DROP COLUMN IF EXISTS segment_version,
DROP COLUMN IF EXISTS segment_updated_at;

COMMIT;
