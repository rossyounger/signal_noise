# Signal/Noise MVP

Signal/Noise is a pipeline for ingesting audio/text content, segmenting it into atomic ideas, and analyzing it using LLMs to test hypotheses and generate analyst POVs.

## Status: Active Development (Hypothesis-Centric Architecture)

**Last Updated:** Dec 15, 2025

### Recent Major Architecture Changes
- **Hypothesis-Centric Schema:** Restructured data model from topic-based to hypothesis-based.
    - `hypotheses` - Standalone, testable propositions (the primary entity).
    - `hypothesis_segment_links` - Stable hypothesis↔segment pairs storing the latest verdict/analysis.
    - `hypothesis_segment_link_runs` - Append-only history of saved analyses per hypothesis↔segment pair.
    - `questions` - Navigation aids that can link to relevant hypotheses (P2 feature).
    - `hypothesis_versions` - Hypothesis edit history (snapshots of hypothesis text/description/reference before updates).
- **External Reference Support:** Hypotheses can now link to external documents (papers, articles, books).
    - Store brief summaries in `description` field.
    - Link to full content via `reference_url` and `reference_type`.
    - LLM analysis can use summary-only (fast) or full reference context (deep).
    - PDF and web page extraction with caching in `hypothesis_reference_cache` table.
- **Frontend Migration:** Moved from Retool to a custom Next.js application (`web/`).
- **Analysis Pipeline:** Integrated LangChain/LangGraph for:
    - Hypothesis Suggestion (`src/analysis/suggestions.py`)
    - Evidence Analysis (`src/analysis/hypothesis.py`)
    - Reference Content Fetching (`src/analysis/reference_fetcher.py`)
    - Analyst POV Generation (Draft placeholder in API)
- **Segmentation Workbench:** Manual text selection and segment creation from document HTML content.
- **Database Schema:** See `sql/005_add_hypothesis_references.sql` for the latest migration.

## Completed Features

### 1. Ingestion & Transcription
- [x] Podcast RSS ingestion (`scripts/run_ingestion_worker.py`)
- [x] Text/HTML ingestion (`src/ingest_stratechery.py`)
- [x] Transcription queue processing (OpenAI Whisper / AssemblyAI)
- [x] Manual segmentation logic (Text & HTML offsets)

### 2. Backend API (`src/api.py`)
- [x] **Segments:** List (`GET /segments`), Fetch (`GET /segments/{id}`), Create (`POST /segments`)
- [x] **Hypotheses:**
    - List All (`GET /hypotheses`) - Returns all hypotheses with evidence counts and reference metadata.
    - Create (`POST /hypotheses`) - Create new hypothesis with optional reference URL/type.
    - Update (`PATCH /hypotheses/{id}`) - Edit hypothesis text/description/reference fields (ID is stable). Writes edit history to `hypothesis_versions`.
    - Delete (`DELETE /hypotheses/{id}`) - Delete hypothesis and all related evidence (CASCADE).
    - Get Evidence (`GET /hypotheses/{id}/evidence`) - Get latest evidence state per segment for a hypothesis (stale/current based on hypothesis updates).
    - Get Reference (`GET /hypotheses/{id}/reference`) - Fetch full reference document (cached).
    - Suggest (`POST /segments/{id}/hypotheses:suggest`) - LLM-based hypothesis suggestions.
    - Save Evidence (`POST /segments/{id}/evidence`) - Link segment to hypothesis with verdict.
- [x] **Questions (Fully Implemented):**
    - List (`GET /questions`) - List all questions with hypothesis counts.
    - Create (`POST /questions`) - Create a question.
    - Delete (`DELETE /questions/{id}`) - Delete question and its hypothesis links.
    - Get Hypotheses (`GET /questions/{id}/hypotheses`) - Get all hypotheses linked to a question.
    - Link (`POST /questions/{id}/hypotheses`) - Link hypothesis to question.
- [x] **Analysis:**
    - Check Hypothesis (`POST /analysis:check_hypothesis`) - Analyzes segment against hypothesis with optional full reference context.
    - Generate POV (`POST /analysis:generate_pov`) - *Draft placeholder logic*.
- [x] **Data Access:**
    - Documents (`GET /documents`) - List with segment counts, archive support (`PATCH /documents/{id}/archive`)
    - Document Content (`GET /documents/{id}/content`) - Returns `content_text` and `content_html`
    - Document Segments (`GET /documents/{id}/segments`) - Returns all segments for a document
    - Sources (`GET /sources`) - List all sources
- [x] **Ingestion:** Queue ingestion requests (`POST /ingest-requests`) for selected sources

### 3. Frontend UI (`web/`)
- [x] **Navigation:** Unified Header (Segments, Hypotheses, Questions, Documents, Sources).
- [x] **Segments List:** Table view of all segments (`/`).
- [x] **Hypothesis Analysis Workbench:** (`/segments/[id]/analyze`)
    - Staging table for hypotheses (Existing + Suggested + Linked).
    - Editable fields for Hypothesis Text & Description (Markdown support).
    - External reference indicator with link to full document.
    - "Use full reference document" toggle for deep analysis (includes complete paper).
    - "Run Evidence Analysis" button with AI verdict generation.
    - Analysis mode badge showing whether summary or full reference was used.
    - "Save Evidence" updates `hypothesis_segment_links` and appends to `hypothesis_segment_link_runs`.
    - Hypothesis selection checkboxes for selective saving.
- [x] **Hypotheses Page:** (`/hypotheses`)
    - List all hypotheses with evidence counts.
    - Create new hypotheses with optional external reference links (URL, type).
    - Delete hypotheses with double confirmation.
    - Visual indicators for hypotheses with external references.
    - Multi-paragraph description support for complex papers.
- [x] **Hypothesis Evidence Page:** (`/hypotheses/[id]/evidence`) - View evidence trail for a hypothesis.
- [x] **Questions Page:** (`/questions`)
    - List all questions with hypothesis counts.
    - Create new questions.
    - Delete questions with double confirmation.
    - "Analyze Question" button links to question analysis page.
- [x] **Question Analysis Page:** (`/questions/[id]/analyze`)
    - View all hypotheses linked to the question.
    - Link existing hypotheses via modal (same pattern as segment analyzer).
    - "View Evidence" button for each hypothesis.
    - Reference indicators for hypotheses with external documents.
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

3. **Hypothesis Evidence Visualization:**
   - Better visualization of evidence trail over time.
   - Verdict distribution charts.

4. **Polishing UI:**
   - Better error handling and loading states.
   - Authentication (currently open).

## Setup & Running

1. **Database Migration:**
   ```bash
   # Run migrations in order
   psql $SUPABASE_DB_URL < sql/004_hypothesis_centric_schema.sql
   psql $SUPABASE_DB_URL < sql/005_add_hypothesis_references.sql
   psql $SUPABASE_DB_URL < sql/006_hypothesis_versions.sql
   psql $SUPABASE_DB_URL < sql/007_hypothesis_segment_links.sql
   
   # Optional: Add Big World Hypothesis example
   export PYTHONPATH=.
   python3 scripts/add_bigworld_hypothesis.py
   ```

2. **Backend API:**
   ```bash
   # In root directory
   export PYTHONPATH=.
   python3 -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --reload
   ```

3. **Frontend:**
   ```bash
   cd web
   npm run dev
   # Runs on http://localhost:3000
   ```

4. **Ingestion Worker** (run in a separate terminal):
   ```bash
   # In root directory - processes queued ingestion jobs
   export PYTHONPATH=.
   python -m scripts.run_ingestion_worker
   ```
   The worker polls the `ingestion_requests` table and runs source ingestion for queued jobs. Use the Sources page "Refresh Selected" button to queue ingestion requests.
