BEGIN;

-- Update existing segments with 'proposed' status to 'raw text'
UPDATE segments
SET segment_status = 'raw text'
WHERE segment_status = 'proposed';

-- Change the default value of the segment_status column to 'raw text'
ALTER TABLE segments
ALTER COLUMN segment_status SET DEFAULT 'raw text';

COMMIT;
