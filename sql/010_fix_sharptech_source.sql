BEGIN;

-- Set the source type for 'Sharp Tech Podcast' to 'podcast'
UPDATE sources
SET type = 'podcast'
WHERE name = 'Sharp Tech Podcast';

-- Update existing documents from 'Sharp Tech Podcast' to have the correct media type
UPDATE documents
SET original_media_type = 'podcast_audio'
WHERE source_id = (SELECT id FROM sources WHERE name = 'Sharp Tech Podcast');

COMMIT;
