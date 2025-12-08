<!-- 2ca5c07e-64d8-45e8-b1a7-7c0d87a13d38 6ba87525-bccc-4316-ac33-892f6e82bf2d -->
# Plan: Scalable Segment Analysis Pipeline

This plan outlines the architecture and implementation steps for building a modular and scalable analysis pipeline for document segments, as requested.

## 1. Overview

The goal is to create a system where a user can select a segment and trigger a series of analytical steps (e.g., labeling, summarization, hypothesis testing). The results are then saved back to the database.

The proposed architecture extends the existing worker pattern. A new API endpoint will create jobs in a new `analysis_requests` table. A generic `analysis_worker` will process these jobs, running the segment through a configurable series of "Analysis Modules." This design is modular, allowing new analysis types to be added easily.

This directly addresses your concept of a "Model-Context-Protocol" (MCP). Each analysis module will be a self-contained implementation of an MCP: it will define the **Model** (e.g., `Claude 3 Sonnet` for summarization), the **Context** (the data passed to the model, like the segment text and a prompt template), and the **Protocol** (how to call the model API and parse its output).

## 2. Proposed Architecture

The flow will be as follows:

1.  **Trigger**: User clicks "Analyze Segment" in Retool for a specific segment.
2.  **API Call**: Retool calls a new FastAPI endpoint: `POST /segments/{segment_id}/analyze`. The request body can specify which analyses to run (e.g., `["labeling", "summary"]`).
3.  **Queueing**: The API endpoint creates a new row in an `analysis_requests` table with `status='pending'`. It will create one request per analysis type requested.
4.  **Processing**: A new background worker, `scripts/run_analysis_worker.py`, polls the `analysis_requests` table for pending jobs.
5.  **Execution**: For each job, the worker retrieves the segment text, invokes the appropriate Analysis Module (e.g., `SummarizationModule`), and calls the selected AI model.
6.  **Save Results**: The worker saves the output into a new `segment_analyses` table, linking back to the original segment.
7.  **Display**: Retool can then join the `segments` table with `segment_analyses` to display the results.

## 3. Database Schema Changes

We'll need a new migration file to create tables for queueing analysis requests and storing their results. A new table for results, `segment_analyses`, is preferred over adding more JSONB columns to `segments` to keep the core `segments` table clean and to allow multiple analyses of different types per segment.

A new file `sql/007_create_analysis_tables.sql` will be created.

## 4. API and Backend Implementation

### FastAPI Endpoint (`src/api.py`)

A new endpoint will be added to handle analysis requests. It will be responsible for creating the job entries in the `analysis_requests` table.

### Analysis Worker (`scripts/run_analysis_worker.py`)

A new worker script, similar to the existing ones, will be created. It will contain a dispatcher that maps an `analysis_type` string to the corresponding Python function or class that executes the analysis. This promotes modularity. A new `src/analysis/` directory will be created to house the logic for different analysis types.

## 5. Tooling and Technology Recommendations

This is where we can leverage cutting-edge tools to implement the "MCP" concept effectively.

-   **AI Model Interaction & Orchestration**:
    -   **Recommendation**: Use **`Instructor`** with Pydantic. It's a lightweight but powerful library that sits on top of an AI client (like OpenAI's or Anthropic's) to guarantee structured, validated JSON output from LLMs. This is ideal for ensuring the `result` JSONB in `segment_analyses` has a predictable schema.
    -   **Alternative**: `LangChain` is a popular, comprehensive framework, but its heavy abstractions can sometimes add unnecessary complexity. For this project's goal of clear, modular components, `Instructor` offers more direct control.
    -   **Why `Instructor`?**: It forces you to define a Pydantic model for your desired output. This model acts as both a response parser and a key part of the prompt, making the "Protocol" part of your MCP explicit and reliable.

-   **AI Models (The "M" in MCP)**:
    -   **For Summarization & General Reasoning**: **Anthropic's Claude 3 family (Haiku, Sonnet, Opus)** are excellent choices. Sonnet provides a great balance of cost and performance.
    -   **For Speed/Cost-sensitive Labeling**: **OpenAI's GPT-4o or GPT-3.5-Turbo** are fast and cost-effective.
    -   **Flexibility**: The architecture will allow the model to be specified per analysis type, or even per request, giving you the ability to choose the best tool for each job.

-   **The "Context" in MCP**:
    -   This is about prompt engineering. Each analysis module will have its own prompt template. Using f-strings or a simple templating engine within each module is sufficient and maintains clarity.

Please review this plan and let me know if you'd like to proceed or make any adjustments.

### To-dos

- [ ] Create a new SQL migration file (`sql/007_create_analysis_tables.sql`) to define the `analysis_requests` and `segment_analyses` tables.
- [ ] Add the new `POST /segments/{segment_id}/analyze` endpoint to the FastAPI application in `src/api.py`.
- [ ] Create a new `src/analysis/` directory and implement the first two analysis modules: `summarizer.py` and `labeler.py`, using `Instructor` and Pydantic for structured output.
- [ ] Create the new background worker script, `scripts/run_analysis_worker.py`, to process jobs from the `analysis_requests` table.
- [ ] Update project dependencies in `pyproject.toml` to include new libraries like `instructor` and `anthropic`.