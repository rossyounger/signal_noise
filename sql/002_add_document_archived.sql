-- Add is_archived column to documents table for soft-delete functionality
-- Documents marked as archived will be hidden from the default UI view

ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE;

-- Index for efficient filtering of non-archived documents
CREATE INDEX IF NOT EXISTS idx_documents_is_archived ON documents (is_archived) WHERE is_archived = FALSE;

