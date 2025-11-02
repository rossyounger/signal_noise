### RESTART INSTRUCTIONS - FOR ROSS ONLY NOT PART OF README

## virtualenv exists
python3 -m venv .venv  
source .venv/bin/activate 
pip install -r requirements.txt 

## spawn extra terminals from project root
open -a "Terminal" /Users/rossyounger/Code/signal_noise  # spawn extra terminals from project root

## turn on four terminals using appscript
  # terminal 1: FastAPI backend on localhost:8000
  # terminal 2: ingestion worker
  # terminal 3: transcription worker
  # terminal 4: expose API to Retool cloud

uvicorn src.api:app --reload
python -m scripts.run_ingestion_worker
python -m scripts.run_transcription_worker
ngrok http http://127.0.0.1:8000

# Signal/Noise Pipeline

This project implements the Signal/Noise MVP pipeline: Ingest → Segment → Save → Review → Label → Search. The entire workflow is designed to be managed from a Retool user interface, powered by a Python FastAPI backend and asynchronous worker processes.

## Architecture Overview

The system is composed of three main parts:

1.  **FastAPI Backend (`src/api.py`):** A lightweight API server that provides endpoints for Retool to interact with. It handles requests for ingesting new sources, transcribing audio, and creating segments from text.
2.  **Background Workers (`scripts/`):** Long-running tasks like fetching RSS feeds and running transcription models are handled by independent worker scripts. These scripts poll the database for jobs queued by the API, ensuring the UI remains fast and responsive.
3.  **Retool UI:** The central control panel for the entire pipeline. From Retool, a user can trigger source ingestion, manage the transcription of audio files, and create precise segments from text documents.

## Local Development Setup

### 1. Environment and Dependencies

1.  Create a Python virtual environment: `python3 -m venv .venv`
2.  Activate it: `source .venv/bin/activate`
3.  Install dependencies: `pip install -r requirements.txt`

### 2. Secrets

1.  Copy the example environment file: `cp .env.example .env`
2.  Fill in your credentials in the `.env` file. At a minimum, you need `SUPABASE_DB_URL` and `OPENAI_API_KEY`. If you plan to use AssemblyAI for transcription, also provide `ASSEMBLYAI_API_KEY`.

### 3. Database Migrations

Apply any new SQL migrations located in the `/sql` directory to your Supabase database. You can do this by pasting the SQL code into the Supabase SQL Editor.

### 4. Running the System

To run the full application for development, you will need to run **three separate processes in three separate terminals**. The recommended way to do this is using the integrated terminal within your code editor (like Cursor).

**Terminal 1: API Server (with Auto-Reload)**
This command starts the FastAPI server. The `--reload` flag automatically restarts the server whenever you save a code change, which is ideal for development.
```bash
uvicorn src.api:app --reload
```

**Terminal 2: Ingestion Worker**
This worker polls the database for new source ingestion jobs queued from the Retool UI. Run it as a module from the project root.
```bash
python3 -m scripts.run_ingestion_worker
```

**Terminal 3: Transcription Worker**
This worker polls the database for new audio transcription jobs queued from the Retool UI. Run it as a module from the project root.
```bash
python3 -m scripts.run_transcription_worker
```

Your backend is now fully running and ready to receive requests from your Retool application.

## Retool UI Workflow

The user-facing workflow is managed entirely within Retool, broken down into several pages.

### 1. Sources Page

-   **Purpose:** Trigger the ingestion of new content from RSS feeds.
-   **Actions:**
    1.  A table displays all available sources from the `sources` table.
    2.  The user selects one or more sources.
    3.  Clicking "Refresh Selected Sources" sends a request to the API, which queues jobs for the ingestion worker to process.

### 2. Documents Page

-   **Purpose:** View all ingested content and initiate segmentation or transcription.
-   **Actions:**
    1.  A table displays all articles and podcasts from the `documents` table.
    2.  From here, the user can select documents and navigate to one of two specialized workbenches.

### 3. Transcription Workbench (for Audio)

-   **Purpose:** Create text segments from audio files.
-   **Actions:**
    1.  The user defines a time range (start and end seconds) for a specific audio document.
    2.  Clicking "Transcribe" queues a job for the transcription worker.
    3.  The worker processes the audio segment and saves the resulting text as a new "proposed" segment in the `segments` table.

### 4. Segmentation Workbench (for Text)

-   **Purpose:** Create precise text segments from articles.
-   **Actions:**
    1.  The full text of the selected document is displayed in an editor.
    2.  The user highlights a specific passage of text.
    3.  Clicking "Create Segment from Selection" instantly saves the highlighted text and its position as a new row in the `segments` table.