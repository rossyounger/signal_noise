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
- Manual/CLI scripts already exist (`ingest_stratechery.py`, `ingest_sharptech_podcast.py`).

### FR2 – On-Demand Transcription
- Allow human-triggered transcription for any audio document or segment window.
- CLI workflow:
  1. List audio documents (`scripts/list_audio_documents.py`).
  2. Queue transcription with provider + optional start/end (`scripts/queue_transcription.py`).
  3. Process request via provider adapter (`scripts/run_transcription.py`).
- Providers supported: OpenAI Whisper (<= 23 min) and AssemblyAI (full-length).
- Transcription results:
  - Full runs update `documents.content_text`, append transcript asset, mark `transcript_status='complete'`.
  - Segment runs append transcript snippets to `documents.assets`, store raw text in `transcription_requests.result_text`, set `transcript_status='partial'`.
- `transcription_requests` table records provider, model, timestamps, status, raw text, metadata. Future automation can poll this queue.

### FR3 – Segment (Snippets Generator)
- Split long-form content into topical snippets. For text, plan pre-chunking + LLM regrouping; for audio, run on transcripts once available.
- Each snippet stores `document_id`, offsets (`start_char`, `end_char` for text; timestamps for audio), and raw text.
- Ensure segments can be regenerated to maintain provenance.
- Segment selection flows through Retool: analysts pick `documents` rows and enqueue a request in `segment_generation_requests`; a worker script processes the queue and writes rows to `segments` with `segment_status='proposed'`.
- Source documents track snippet lifecycle via `documents.segment_status` (`not_started`, `queued`, `running`, `generated`, `failed`) and `segment_version` so analysts can filter for items that still need segmentation.

### FR4 – Save Segments
- Persist snippets in a `segments` table with:
  - `document_id`, `text`, `start_offset`, `end_offset`
  - `segment_status` (`proposed`, `final`, `superseded`)
  - `version` integer, `labels` JSONB (empty by default)
  - Provenance metadata (e.g., audio timestamps, HTML path)
- Support updates when segments are refined or superseded.
- Segment generation worker auto-supersedes existing `proposed`/`final` rows before inserting a new version, and updates `documents.segment_status`/`segment_version` to keep the source record of truth.

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

## 5. Data Model Summary

### Core tables
- `sources`: id, name, type, feed_url, ingest_config, default_language, polling_interval, status timestamps.
- `documents`: id, source_id, external_id, ingest_method, original_media_type, original_url, title, author, published_at, content_html, content_text, assets JSONB, transcript_status, ingest_status, provenance JSONB, `segment_status`, `segment_version`, `segment_updated_at`, timestamps.
- `segments` (planned): id, document_id, text, start_offset, end_offset, status, version, labels JSONB, provenance JSONB, timestamps.
- `notes` (planned): id, document_id, segment_id nullable, note_type, text, created_by, timestamps.
- `transcription_requests`: id, document_id, provider, model, start_seconds, end_seconds, status, result_text, metadata JSONB, timestamps.

### Assets JSON schema
- Audio asset example:
  ```json
  {"type": "audio", "url": "https://…mp3", "length": 87703891, "mime_type": "audio/mpeg", "duration": "01:30:50"}
  ```
- Transcript asset example:
  ```json
  {"type": "transcript", "source": "openai:gpt-4o-mini-transcribe", "start_seconds": 2321.0, "end_seconds": 2940.0, "text": "…"}
  ```

## 6. CLI & Developer Tooling

- `python src/ingest_stratechery.py` – article ingestion.
- `python src/ingest_sharptech_podcast.py` – podcast ingestion (audio metadata).
- `python scripts/list_audio_documents.py` – list documents queued for transcription.
- `python scripts/queue_transcription.py <doc_id> [--provider|--start|--end]` – enqueue transcription.
- `python scripts/run_transcription.py <request_id>` – process queued transcription.
- `.env` requires: `SUPABASE_DB_URL`, `STRATECHERY_FEED_URL`, `SHARPTECH_PODCAST_FEED_URL`, `OPENAI_API_KEY`, optional `ASSEMBLYAI_API_KEY`.
- Retool setup: connect to Supabase, expose documents/segments/requests tables.

## 7. Next Steps

1. Implement `segments` table & generation pipeline.
2. Build Retool review app with transcription queue control.
3. Add AI labeling helpers and storage.
4. Implement basic search (SQL) and plan indexing for later.
5. Consider background worker (cron) to process queued transcriptions automatically.

---

# Cursor Rules for Signal/Noise

```
# Project intent
Implement the Signal/Noise MVP pipeline: Ingest → Segment → Save → Review → Label → Search, with manual transcription support.

# Folder map
/src              # ingestion modules, future segmentation code
/scripts          # CLI utilities (ingest, transcription)
/sql              # database migrations (/sql/00x_*.sql)
/docs/PRD.md      # product specification (single source of truth)
/tests            # pytest suites
/configs          # Retool or environment config (if any)

# Canonical references
docs/PRD.md defines requirements and data model expectations.
Segments must capture: document_id, start/end offsets, status, version, labels JSONB, provenance.
Transcriptions flow through scripts/ queue + run; assets JSON structure must remain consistent.

# Coding constraints
Python 3.11
Supabase Postgres backend
feedparser / requests / psycopg for ingestion, optional AssemblyAI/OpenAI clients
Lint with ruff, tests with pytest
Future FastAPI service should read from existing models.

# Agent guidance
Align all changes with docs/PRD.md.
Preserve provenance; no raw blob duplication.
Prefer explicit scripts/migrations over ad-hoc SQL.
Document new CLI usage in README when functionality changes.
```
