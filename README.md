# signal_noise Quick Start

## Environment Setup
1. Create the virtual environment: `python -m venv .venv`
2. Activate it (macOS/Linux): `source .venv/bin/activate`
3. Upgrade pip: `python -m pip install --upgrade pip`
4. Install dependencies: `pip install -r requirements.txt`

## Secrets
- Copy `.env.example` to `.env`
- Fill in real credentials (keep `.env` out of version control)
- `python-dotenv` loads these variables at runtime

## Tooling
- Tests: `pytest`
- Lint: `ruff check .`
- Type check: `mypy .`

Source code lives in `src/`; place new agents under `src/agents/`. Tests belong in `tests/`. Update `.env.example` and `requirements.txt` whenever secrets or dependencies change.

## Ingestion Scripts

- `python src/ingest_stratechery.py`
  - Pulls the Stratechery article RSS feed.
  - Requires `STRATECHERY_FEED_URL` and `SUPABASE_DB_URL` in your environment.
  - Stores cleaned HTML/text in the `documents` table (one row per article).

- `python src/ingest_sharptech_podcast.py`
  - Pulls Sharp Tech podcast episodes (audio metadata only).
  - Requires `SHARPTECH_PODCAST_FEED_URL` (personalized token) and `SUPABASE_DB_URL`.
  - Inserts each episode into `documents` with an `assets` entry containing the MP3 URL and marks `transcript_status='pending'`.

Each script is safe to rerun; it upserts on `(source_id, external_id)`.

## Audio Transcription Flow

1. **List candidates**
   ```bash
   python scripts/list_audio_documents.py
   ```
   Copy the `id` (UUID) of the episode you care about.

2. **Queue a transcription job**
   ```bash
   python scripts/queue_transcription.py <document_id> \
     --provider openai \
     --start 15:00 --end 25:00  # optional segment
   ```
   - `--provider` supports `openai` (Whisper) or `assembly` (AssemblyAI).
   - `--model` is optional; defaults to `gpt-4o-mini-transcribe` for OpenAI.
   - The command writes a row into `transcription_requests` and prints the request UUID.

3. **Run the transcription**
   ```bash
   python scripts/run_transcription.py <request_id>
   ```
   - Downloads the MP3, trims to the requested window if provided, calls the provider, and updates both `transcription_requests` and the `documents` row (`content_text`, `transcript_status`, `assets`).
   - Requires API keys: `OPENAI_API_KEY` for Whisper, `ASSEMBLYAI_API_KEY` for AssemblyAI, and `ffmpeg` on PATH for segment trimming.

### After Transcription

- Each request writes the raw transcript to `transcription_requests.result_text`. This is the fastest way to copy/paste the output.
- A `transcript` asset is appended to the source document (`documents.assets`). The entry records provider, timestamps, and text.
  - Full-length runs (no `--start/--end`) also update `documents.content_text` and mark `transcript_status='complete'`.
  - Segment runs leave `content_text` untouched and set `transcript_status='partial'`, so you can queue multiple snippets for the same episode without overwriting anything.
- Re-running the same document just adds more transcript assets; nothing is deleted automatically. Use Supabase Studio or downstream code to view/merge snippets as needed.

The workflow is manual by design: copy the document ID from Supabase (or the list script), queue the job, run it. Later you can wire this into a cron job or UI without changing the commands.

## Segment Generation Flow (FR3–FR5)

1. **Select documents**
   - In Retool, select one or more `documents` rows and trigger a query that inserts into the `segment_generation_requests` table (one row per document). The same insert can be performed from the CLI:
     ```bash
     python scripts/queue_segments.py <doc_id_1> <doc_id_2>
     ```
     Optional flags: `--created-by` (your initials) and `--options '{"prefer_transcript": true}'`.
     - The queue script skips anything already pending and sets `documents.segment_status='queued'` so you can filter for items awaiting processing.

2. **Process the queue**
   ```bash
   python scripts/run_segmenter.py --once  # process a single pending request
   python scripts/run_segmenter.py         # keep running, polling every 5s
   ```
   - Pulls the next `pending` request, finds the best text source (full article text or latest transcript asset), chunks it, optionally calls the LLM regrouping helper, and writes `segments` rows with `segment_status='proposed'`.
   - Existing `proposed`/`final` segments for that document are marked `superseded` and the version number is incremented so edits stay auditable.
   - The worker updates the parent `documents` row (`segment_status='running'` → `generated` or `failed`, plus `segment_version`/`segment_updated_at`).

3. **Review & edit**
   - Retool surfaces the destination `segments` table. Analysts tweak `text`, `start_offset`, `end_offset`, add notes/labels, and promote status to `final` when satisfied.
   - Retry any failed queue items by updating `segment_generation_requests.status` back to `pending` (the document row stays `queued` until processed again).

### Worker options

`run_segmenter.py` supports:
- `--document-id=<uuid>` to restrict processing to a single document.
- `--poll-interval=<seconds>` to adjust the background loop cadence.
- `--log-level=DEBUG` for verbose troubleshooting.

The worker expects `SUPABASE_DB_URL` (or `--dsn`) to point at the Supabase instance.

### Table additions

- `segments`: stores generated snippets (`document_id`, offsets, `segment_status`, `version`, `labels`, `provenance`).
- `segment_generation_requests`: simple queue for pending segmentation actions (`document_id`, `created_by`, `options`, status/error state`).
- `documents` now tracks snippet lifecycle with `segment_status`, `segment_version`, and `segment_updated_at`, making it easy to find unsegmented sources.

Retool should expose both tables so you can: pick documents to queue, monitor status, and edit the resulting snippets without leaving the UI.