# Signal/Noise MVP PRD

## 1. Overview

**Goal:** Build the Signal/Noise pipeline that ingests opinionated sources (initially Stratechery and Sharp Tech), normalizes content, creates ontology-ready snippets, and exposes them for manual review, labeling, and search. The MVP targets fast evidence retrieval with provenance; ontology-aware reasoning is deferred.

**Pipeline:** Ingest → Segment → Save → Review → Label → Search

## 2. Jobs-To-Be-Done

1. **Find evidence fast** – Search curated snippets with provenance, copy the exact excerpt in seconds, and trust the source trail.
2. **Prepare for ontology-aware queries** (future) – Structure relationships across companies, products, markets, and signals.
3. **Transcribe on demand** – Pull audio segments into text when a podcast conversation contains useful insights, without transcribing full episodes by default.

## 3. Functional Requirements

### FR1 – Ingest & Normalize
- Adapter-based ingestion for Stratechery articles (RSS) and Sharp Tech podcast feed.
- Store one row per source artifact in `documents` with raw HTML, cleaned text, provenance metadata, and `assets` JSON (audio URLs, transcripts, etc.).
- Deduplicate via `(source_id, external_id)`; track ingest status (`pending`, `ok`, `failed`).
- Maintain `sources` table for feed metadata (type, URL, polling cadence).
- **New Workflow:** Ingestion is triggered from a Retool UI. A button press calls a new FastAPI endpoint, which queues requests in an `ingestion_requests` table. A background worker (`scripts/run_ingestion_worker.py`) processes this queue.

### FR2 – On-Demand Transcription
- Allow human-triggered transcription for any audio document or segment window from within Retool.
- **New Workflow:**
  1. User selects an audio document in Retool and defines a start/end time in the "Transcription Workbench."
  2. A "Transcribe" button calls a FastAPI endpoint (`/transcription-requests`), creating a job in the `transcription_requests` table.
  3. A background worker (`scripts/run_transcription_worker.py`) processes the queue.
  4. The output is saved directly as a new row in the `segments` table with `segment_status='proposed'`.
- Providers supported: OpenAI Whisper (<= 23 min) and AssemblyAI (full-length).
- The `transcription_requests` table tracks job status. Requests flow from `pending` → `in_progress` → `completed` or `failed`, and failures record a short error summary in `metadata->>'error'`.

### FR3 – Segment (Snippets Generator)
- Split long-form content into topical snippets.
- **New Workflow for Text:**
  1. User selects a text document in Retool and opens it in the "Segmentation Workbench."
  2. The UI fetches the full document text via a new FastAPI endpoint.
  3. User highlights a passage of text in the Retool UI.
  4. A "Create Segment" button calls a FastAPI endpoint (`/segments`) with the selected text and its character offsets.
  5. The segment is immediately saved to the `segments` table.
- **New Workflow for Audio:** Transcription (FR2) now creates segments directly. The original automated segmentation flow (`run_segmenter.py`) is deferred.

### FR4 – Save Segments
- Persist snippets in a `segments` table with:
  - `document_id`, `text`, `start_offset`, `end_offset`
  - `segment_status` (`proposed`, `final`, `superseded`)
  - `version` integer, `labels` JSONB (empty by default)
  - Provenance metadata (e.g., audio timestamps, HTML path)
- Support updates when segments are refined or superseded.
- Segment updates should refresh `documents.segment_status` via triggers so the source record reflects the newest segment state.

### FR5 – Review (Retool Builder Console)
- Expose Supabase tables via Retool / lightweight UI immediately after save.
- Ability to browse documents, view segments, edit text/offsets, add notes/hypotheses, and enqueue manual actions (e.g., transcription requests).
- Acts as the primary schema-shaping UI during MVP.
- UI includes a queued segments view with retry controls and inline editing/promotion of `segment_status`.

### FR6 – Labeler (AI Assist + Manual)
- Provide labeling workflow inside Retool to tag segments with entities (`company`, `person`, `topic`, etc.).
- Optional AI suggestions stored in `labels` JSONB; human can approve/edit.
- Track label provenance (auto vs manual).

### FR7 – Search & Context Export
- Query finalized segments by source, label, free text.
- Export a curated bundle (snippets + metadata) for downstream LLM prompts.
- Support BM25 or vector indexing later—initial pass can rely on SQL text search.
## 4. Non-Functional Requirements

- **Tech stack:** Python 3.11, Supabase Postgres, feedparser, psycopg, requests, optional AssemblyAI/OpenAI clients.
- **Ops:** CLI-based orchestration for now. Plan Cron/Retool automation later.
- **Performance:** MVP tolerates manual runs; RSS ingestion should complete within minutes, transcription limited by provider throughput.
- **Security:** Keep API keys in `.env`; never commit secrets. Tokenized feed URLs treated as secrets.

## 5. Architecture & Tooling
- **API Server:** A new FastAPI application (`src/api.py`) provides endpoints for Retool to interact with the database. It handles queuing for ingestion and transcription, and direct creation of manual segments.
- **Background Workers:** Long-running tasks are handled by worker scripts that poll the database:
  - `scripts/run_ingestion_worker.py` for processing `ingestion_requests`.
  - `scripts/run_transcription_worker.py` for processing `transcription_requests`.
- **Retool UI:** The primary user interface for triggering ingestion, transcribing audio, and creating segments from text.

## 6. Data Model Summary

### Core tables
- `sources`: id, name, type, feed_url, ingest_config, default_language, polling_interval, status timestamps.
- `documents`: id, source_id, external_id, ingest_method, original_media_type, original_url, title, author, published_at, content_html, content_text, assets JSONB, transcript_status, ingest_status, provenance JSONB, `segment_status`, timestamps.
- `segments`: id, document_id, text, start_offset, end_offset, segment_status (`proposed`/`final`/`superseded`), version, labels JSONB, provenance JSONB, timestamps.
- `notes` (planned): id, document_id, segment_id nullable, note_type, text, created_by, timestamps.
- `transcription_requests`: id, document_id, provider (`openai`/`assemblyai`), model, start_seconds, end_seconds, status (`pending`/`in_progress`/`completed`/`failed`), result_text, metadata JSONB, timestamps.
- `ingestion_requests`: id, source_id, status (`queued`/`in_progress`/`completed`/`failed`), error_message, timestamps.

### Assets JSON schema
- Audio asset example:
  ```json
  {"type": "audio", "url": "https://…mp3", "length": 87703891, "mime_type": "audio/mpeg", "duration": "01:30:50"}
  ```
- Transcript asset example:
  ```json
  {"type": "transcript", "source": "openai:gpt-4o-mini-transcribe", "start_seconds": 2321.0, "end_seconds": 2940.0, "text": "…"}
  ```

## 7. Developer Runbook
- Apply SQL migrations in `/sql` to Supabase in order.
- Populate `.env` with at least `SUPABASE_DB_URL`, `OPENAI_API_KEY`, and optionally `ASSEMBLYAI_API_KEY` for long-form transcription.
- Run the FastAPI server: `uvicorn src.api:app --reload`.
- Run background workers in separate terminals:
  - `python -m scripts.run_ingestion_worker`
  - `python -m scripts.run_transcription_worker`
- Retool connects to these endpoints to queue ingestion/transcription and to review segments. No manual CLI actions are needed beyond the workers above.

## 8. Future Enhancements
1. Improve document-level `segment_status` trigger logic to reflect true aggregate state.
2. Revisit automated segmentation for long-form text and audio regrouping.
3. Expand Retool review tools (bulk labeling, search filters, retry controls).
