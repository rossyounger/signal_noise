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