# Signal/Noise MVP

Signal/Noise is a pipeline for ingesting audio/text content, segmenting it into atomic ideas, and analyzing it using LLMs to generate structured topic knowledge and analyst POVs.

## Status: Active Development (Migration Phase)

**Last Updated:** Dec 5, 2025

### Recent Major Architecture Changes
- **Frontend Migration:** Moved from Retool to a custom Next.js application (`web/`).
- **Topic-Centric Schema:** Shifted data model from simple segments to a robust topic history (`topics_history`) and analysis flow.
- **Analysis Pipeline:** Integrated LangChain/LangGraph for:
    - Topic Suggestion (`src/analysis/suggestions.py`)
    - Hypothesis Checking (`src/analysis/hypothesis.py`)
    - Analyst POV Generation (Draft placeholder in API)
- **Segmentation Workbench:** Manual text selection and segment creation from document HTML content.
- **Database Schema:** Consolidated migrations into baseline schema (`sql/001_baseline_schema.sql`).
- **Code Cleanup:** Removed abandoned persona-based analysis pipeline code.

## Completed Features

### 1. Ingestion & Transcription
- [x] Podcast RSS ingestion (`scripts/run_ingestion_worker.py`)
- [x] Text/HTML ingestion (`src/ingest_stratechery.py`)
- [x] Transcription queue processing (OpenAI Whisper / AssemblyAI)
- [x] Manual segmentation logic (Text & HTML offsets)

### 2. Backend API (`src/api.py`)
- [x] **Segments:** List (`GET /segments`), Fetch (`GET /segments/{id}`), Create (`POST /segments`)
- [x] **Topics:**
    - List Home View (`GET /topics`) - Returns latest topic state.
    - Create Manual Topic (`POST /topics`) - Create new `topic_ids`.
    - Suggest Topics (`POST /segments/{id}/topics:suggest`) - LLM-based suggestion.
    - Save Analysis (`POST /segments/{id}/topics`) - Writes to `topics_history`.
- [x] **Analysis:**
    - Check Hypothesis (`POST /analysis:check_hypothesis`) - Confirms/Refutes user hypothesis.
    - Generate POV (`POST /analysis:generate_pov`) - *Draft placeholder logic*.
- [x] **Data Access:**
    - Documents (`GET /documents`) - List with segment counts, archive support (`PATCH /documents/{id}/archive`)
    - Document Content (`GET /documents/{id}/content`) - Returns `content_text` and `content_html`
    - Document Segments (`GET /documents/{id}/segments`) - Returns all segments for a document
    - Sources (`GET /sources`) - List all sources
- [x] **Ingestion:** Queue ingestion requests (`POST /ingest-requests`) for selected sources

### 3. Frontend UI (`web/`)
- [x] **Navigation:** Unified Header (Segments, Topics, Documents, Sources).
- [x] **Segments List:** Table view of all segments (`/`).
- [x] **Topic Analysis Workbench:** (`/segments/[id]/analyze`)
    - Staging table for topics (Existing + Suggested).
    - Editable fields for Description & Hypothesis (Markdown support).
    - "Check Hypothesis" button with AI verification.
    - "Save Changes" persisting to `topics_history`.
    - Topic selection checkboxes for selective saving.
- [x] **Topics Page:** (`/topics`) - List existing topics, create new ones manually.
- [x] **Documents Page:** (`/documents`)
    - Table view with segment counts, preview text, and metadata.
    - Archive functionality (removes from active view).
    - Action buttons: "Segment" (links to Segmentation Workbench), "Transcribe" (links to Transcription Workbench).
    - Clickable article titles linking to original URLs.
- [x] **Segmentation Workbench:** (`/documents/[documentId]/segmentation`)
    - Full HTML document viewer with selectable text.
    - Visual text selection with persistent highlighting.
    - "Create Segment" button with live-updating offset display.
    - Segments table showing existing segments for the document.
    - Uses backend's `find_html_fragment` for accurate HTML extraction.
- [x] **Sources Page:** (`/sources`)
    - List all sources with metadata.
    - Row selection with "Refresh Selected" button.
    - Queues ingestion requests for selected sources.

## Upcoming / Pending Implementation

1. **Transcription Workbench:**
   - Placeholder page exists at `/documents/[documentId]/transcription`.
   - Needs implementation for audio transcription workflow.

2. **Analyst POV Logic:**
   - The `generate_pov` endpoint currently returns dummy data. Need to implement the real LangGraph agent to generate synthesis.

3. **Refining Topic History:**
   - Visualizing the evolution of a topic over time (showing the history log).
   - "Merge Topics" functionality (future).

4. **Polishing UI:**
   - Better error handling and loading states.
   - Authentication (currently open).

## Setup & Running

1. **Backend API:**
   ```bash
   # In root directory
   export PYTHONPATH=.
   python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --reload
   ```

2. **Frontend:**
   ```bash
   cd web
   npm run dev
   # Runs on http://localhost:3000
   ```

3. **Ingestion Worker** (run in a separate terminal):
   ```bash
   # In root directory - processes queued ingestion jobs
   export PYTHONPATH=.
   python -m scripts.run_ingestion_worker
   ```
   The worker polls the `ingestion_requests` table and runs source ingestion for queued jobs. Use the Sources page "Refresh Selected" button to queue ingestion requests.
