BEGIN;

-- Set a default value for segment_status on new documents
ALTER TABLE documents
ALTER COLUMN segment_status SET DEFAULT 'Not Started';

-- Update existing documents that might have a NULL status
UPDATE documents
SET segment_status = 'Not Started'
WHERE segment_status IS NULL;

COMMIT;

