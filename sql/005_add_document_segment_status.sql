BEGIN;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS segment_status TEXT NOT NULL DEFAULT 'not_started',
    ADD COLUMN IF NOT EXISTS segment_version INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS segment_updated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_documents_segment_status
    ON documents (segment_status);

-- created_by column added in earlier migration; keep for idempotency when rerun
ALTER TABLE segment_generation_requests
    ADD COLUMN IF NOT EXISTS created_by TEXT;

WITH ranked_pending AS (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY created_at ASC) AS rn
    FROM segment_generation_requests
    WHERE status = 'pending'
)
DELETE FROM segment_generation_requests s
USING ranked_pending rp
WHERE s.id = rp.id
  AND rp.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_segment_requests_pending_unique
    ON segment_generation_requests (document_id)
    WHERE status = 'pending';

WITH latest_segments AS (
    SELECT document_id,
           MAX(version) AS max_version,
           MAX(updated_at) AS last_updated
    FROM segments
    GROUP BY document_id
),
updated_docs AS (
    UPDATE documents d
    SET segment_status = 'generated',
        segment_version = ls.max_version,
        segment_updated_at = COALESCE(ls.last_updated, now())
    FROM latest_segments ls
    WHERE d.id = ls.document_id
    RETURNING d.id
)
UPDATE documents d
SET segment_status = 'queued',
    segment_updated_at = now()
WHERE d.id IN (
    SELECT DISTINCT document_id
    FROM segment_generation_requests
    WHERE status = 'pending'
)
  AND d.id NOT IN (SELECT id FROM updated_docs);

UPDATE documents d
SET segment_status = 'running',
    segment_updated_at = now()
WHERE d.id IN (
    SELECT DISTINCT document_id
    FROM segment_generation_requests
    WHERE status = 'running'
);

UPDATE documents d
SET segment_status = 'failed',
    segment_updated_at = now()
WHERE d.id IN (
    SELECT DISTINCT document_id
    FROM segment_generation_requests
    WHERE status = 'failed'
);

COMMIT;
