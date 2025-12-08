from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from src.html_offsets import find_html_fragment
from src.analysis.suggestions import suggest_topics as run_suggest_topics, TopicSuggestionModel
from src.analysis.hypothesis import check_hypothesis as run_check_hypothesis

# Load .env from project root
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path, override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection pool
db_pool: AsyncConnectionPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection pool."""
    global db_pool
    db_pool = None
    conn_string = os.environ.get("SUPABASE_CONN_STRING") or os.environ.get("SUPABASE_DB_URL")
    if not conn_string:
        logger.error("SUPABASE_CONN_STRING or SUPABASE_DB_URL not found in environment variables.")
        # We don't raise here to allow the app to start and print logs, 
        # but subsequent DB calls will fail.
    else:
        try:
            db_pool = AsyncConnectionPool(conninfo=conn_string, open=False)
            await db_pool.open()
            logger.info("Database connection pool created.")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")

    yield {"db_pool": db_pool}

    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed.")

app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Allow our Next.js front-end
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Add this middleware to help with running behind a proxy like ngrok
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")


def _require_pool() -> AsyncConnectionPool:
    if db_pool is None:
        raise RuntimeError("Database pool has not been initialised yet.")
    return db_pool


# --- Data Models (Refactored for Versioning) ---

class TopicHomeView(BaseModel):
    """Represents the latest version of a topic for the home page."""
    topic_id: str
    latest_name: str
    latest_description: str | None
    latest_user_hypothesis: str | None
    last_updated_at: datetime
    segment_count: int

class GeneratePovRequest(BaseModel):
    segment_id: str
    topic_name: str
    description: str | None
    user_hypothesis: str | None

class GeneratePovResponse(BaseModel):
    pov_summary: str
    pov_id: str # The ID of the draft record in persona_topic_povs

class CheckHypothesisRequest(BaseModel):
    segment_text: str
    topic_name: str
    user_hypothesis: str

class CheckHypothesisResponse(BaseModel):
    analysis_text: str

class TopicHistoryPayload(BaseModel):
    topic_id: str | None # null if it's a new topic
    name: str
    description: str | None
    user_hypothesis: str | None
    summary_text: str | None = None # This is where the hypothesis analysis goes
    pov_id: str | None # The ID of the draft POV run, if one was generated

class SaveTopicsHistoryRequest(BaseModel):
    topics: List[TopicHistoryPayload]

class TopicSuggestion(BaseModel):
    topic_id: str | None = None
    name: str
    source: str # 'existing' | 'generated'
    description: str | None = None
    user_hypothesis: str | None = None
    summary_text: str | None = None # Pre-filled analysis if available

class SuggestTopicsResponse(BaseModel):
    suggestions: List[TopicSuggestion]

class TopicCreate(BaseModel):
    name: str
    description: str | None = None
    user_hypothesis: str | None = None

class TopicResponse(BaseModel):
    topic_id: str

# --- Documents & Sources Models ---

class DocumentList(BaseModel):
    id: str
    source_title: str | None
    title: str | None
    author: str | None
    published_at: datetime | None
    created_at: datetime
    content_text_preview: str | None
    original_url: str | None
    segment_count: int

class SourceList(BaseModel):
    id: str
    name: str | None
    type: str
    url: str | None
    last_polled: datetime | None
    created_at: datetime


# --- Ingestion & Transcription Workflow (Existing Code) ---


class IngestRequest(BaseModel):
    source_ids: list[str] = Field(..., min_length=1)


class IngestResponse(BaseModel):
    queued_jobs: int


@app.post("/ingest-requests", status_code=202)
async def queue_ingestion(req: IngestRequest) -> IngestResponse:
    """Queue ingestion requests for a list of sources."""
    insert_sql = """
        INSERT INTO ingestion_requests (source_id, status)
        VALUES (%(source_id)s, 'queued')
    """
    params = [{"source_id": s_id} for s_id in req.source_ids]
    pool = _require_pool()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(insert_sql, params)
        return IngestResponse(queued_jobs=len(req.source_ids))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Transcription Workflow ---


class TranscriptionRequest(BaseModel):
    document_id: str
    provider: str = "openai"
    model: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None


class TranscriptionResponse(BaseModel):
    request_id: str


@app.post("/transcription-requests", status_code=202)
async def queue_transcription(req: TranscriptionRequest) -> TranscriptionResponse:
    """Queue a new transcription request."""
    insert_sql = """
        INSERT INTO transcription_requests
            (document_id, provider, model, start_seconds, end_seconds)
        VALUES (%(doc_id)s, %(provider)s, %(model)s, %(start)s, %(end)s)
        RETURNING id
    """
    params = {
        "doc_id": req.document_id,
        "provider": req.provider,
        "model": req.model,
        "start": req.start_seconds,
        "end": req.end_seconds,
    }
    pool = _require_pool()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(insert_sql, params)
                result = await cur.fetchone()
                if not result:
                    raise HTTPException(status_code=500, detail="Failed to retrieve request ID after insert.")
                request_id = str(result[0]) 
        return TranscriptionResponse(request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Manual Segmentation Workflow ---


class Segment(BaseModel):
    id: str
    document_id: str
    title: str
    author: str | None = None
    text: str
    created_at: datetime
    published_at: datetime | None = None


class DocumentContent(BaseModel):
    document_id: str
    content_text: str
    content_html: str | None = None


class SegmentDetail(BaseModel):
    id: str
    document_id: str
    text: str
    content_html: str | None = None


class SegmentWorkbenchContent(BaseModel):
    segment: SegmentDetail
    document: DocumentContent


@app.get("/documents/{document_id}/content")
async def get_document_content(document_id: str) -> DocumentContent:
    """Fetch the text content of a document."""
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT content_text, content_html FROM documents WHERE id = %s",
                (document_id,),
            )
            result = await cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Document not found")
            content_text, content_html = result
            return DocumentContent(
                document_id=document_id,
                content_text=content_text,
                content_html=content_html,
            )


@app.get("/segments/{segment_id}")
async def get_segment_for_workbench(segment_id: str) -> SegmentWorkbenchContent:
    """
    Fetches a segment and the full content of its parent document.
    Primarily used by the Segment Analysis Workbench UI.
    """
    segment_row = await _fetch_segment(segment_id)
    document_content = await get_document_content(str(segment_row["document_id"]))

    segment_detail = SegmentDetail(
        id=str(segment_row["id"]),
        document_id=str(segment_row["document_id"]),
        text=segment_row["text"],
        content_html=segment_row.get("content_html"),
    )

    return SegmentWorkbenchContent(segment=segment_detail, document=document_content)


@app.get("/segments")
async def list_segments() -> list[Segment]:
    """List all segments, joining with documents to get metadata."""
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    s.id,
                    s.document_id,
                    d.title,
                    d.author,
                    s.text,
                    s.created_at,
                    d.published_at
                FROM segments s
                JOIN documents d ON s.document_id = d.id
                ORDER BY s.created_at DESC
                """
            )
            rows = await cur.fetchall()

    results = []
    for row in rows:
        row_dict = dict(row)
        row_dict["id"] = str(row_dict["id"])
        row_dict["document_id"] = str(row_dict["document_id"])
        results.append(Segment(**row_dict))
    return results


class DocumentSegment(BaseModel):
    id: str
    text: str
    segment_status: str
    created_at: datetime


@app.get("/documents/{document_id}/segments", response_model=List[DocumentSegment])
async def list_document_segments(document_id: str) -> list[DocumentSegment]:
    """List all segments for a specific document."""
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, text, segment_status, created_at
                FROM segments
                WHERE document_id = %s
                ORDER BY created_at DESC
                """,
                (document_id,),
            )
            rows = await cur.fetchall()

    results = []
    for row in rows:
        row_dict = dict(row)
        row_dict["id"] = str(row_dict["id"])
        results.append(DocumentSegment(**row_dict))
    return results


class SegmentCreate(BaseModel):
    document_id: str
    text: str
    start_offset: int | None = None
    end_offset: int | None = None
    html: str | None = None


class SegmentResponse(BaseModel):
    segment_id: str


async def _fetch_segment(segment_id: str) -> dict[str, Any]:
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, document_id, text, content_html, offset_kind
                FROM segments
                WHERE id = %s
                """,
                (segment_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Segment not found")
            return row


@app.post("/segments", status_code=201)
async def create_manual_segment(req: SegmentCreate) -> SegmentResponse:
    """Create a new segment manually."""
    pool = _require_pool()
    try:
        async with pool.connection() as conn:
            document_row: dict[str, Any] | None
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT content_text, content_html
                    FROM documents
                    WHERE id = %s
                    """,
                    (req.document_id,),
                )
                document_row = await cur.fetchone()
            if not document_row:
                raise HTTPException(status_code=404, detail="Document not found")

            content_html = document_row.get("content_html")
            html_source = req.html if req.html and req.html.strip() else None
            segment_html: str | None = None
            segment_text_raw = req.text or ""
            segment_text = segment_text_raw.strip()
            requested_start = req.start_offset
            requested_end = req.end_offset
            offset_kind = "text"
            start_offset = req.start_offset
            end_offset = req.end_offset

            if content_html:
                try:
                    mapped = find_html_fragment(
                        content_html,
                        segment_text_raw,
                        html_source,
                        requested_start,
                        requested_end,
                    )
                    if mapped:
                        start_offset = mapped.html_start
                        end_offset = mapped.html_end
                        segment_html = content_html[start_offset:end_offset]
                        offset_kind = "html"
                        cleaned_text = BeautifulSoup(segment_html, "html.parser").get_text().strip()
                    if cleaned_text:
                        segment_text = cleaned_text
                except ValueError:
                    # Could not map, fall back to text offsets
                    pass

            if not segment_text:
                raise HTTPException(status_code=400, detail="Segment text cannot be empty")

            provenance = {
                "source": "manual",
                "selection": {
                    "offset_kind": offset_kind,
                    "stored_start": start_offset,
                    "stored_end": end_offset,
                },
            }

            insert_params = {
                "doc_id": req.document_id,
                "text": segment_text,
                "content_html": segment_html,
                "start": start_offset,
                "end": end_offset,
                "prov": Json(provenance),
                "offset_kind": offset_kind,
            }

            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO segments (
                        document_id,
                        text,
                        content_html,
                        start_offset,
                        end_offset,
                        provenance,
                        segment_status,
                        offset_kind
                    )
                    VALUES (%(doc_id)s, %(text)s, %(content_html)s, %(start)s, %(end)s, %(prov)s, 'proposed', %(offset_kind)s)
                    RETURNING id
                    """,
                    insert_params,
                )
                result = await cur.fetchone()
                if not result:
                    raise HTTPException(status_code=500, detail="Failed to create segment")
                segment_id = str(result[0])
        return SegmentResponse(segment_id=segment_id)
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover - defensive error mapping
        raise HTTPException(status_code=500, detail=str(e))


# --- Topic & Analysis Workflow (New Architecture) ---

@app.get("/topics", response_model=List[TopicHomeView])
async def list_topics_home_view():
    """
    Lists the latest version of each topic for the main "Home POV".
    This is a more complex query that finds the most recent entry in topics_history
    for each unique topic_id.
    """
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                WITH latest_history AS (
                    SELECT
                        DISTINCT ON (topic_id) *
                    FROM topics_history
                    ORDER BY topic_id, created_at DESC
                ),
                topic_stats AS (
                    SELECT
                        topic_id,
                        count(id) as segment_count
                    FROM topics_history
                    GROUP BY topic_id
                )
                SELECT
                    t.id as topic_id,
                    t.name as latest_name,
                    lh.description as latest_description,
                    lh.user_hypothesis as latest_user_hypothesis,
                    COALESCE(lh.created_at, t.created_at) as last_updated_at,
                    COALESCE(ts.segment_count, 0) as segment_count
                FROM topic_ids t
                LEFT JOIN latest_history lh ON t.id = lh.topic_id
                LEFT JOIN topic_stats ts ON t.id = ts.topic_id
                ORDER BY t.name;
                """
            )
            rows = await cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d['topic_id'] = str(d['topic_id'])  # Convert UUID to string
        results.append(TopicHomeView(**d))
    return results

@app.post("/topics", status_code=201)
async def create_topic(req: TopicCreate) -> TopicResponse:
    """
    Creates a new topic manually.
    """
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            # 1. Create the evergreen topic ID
            try:
                await cur.execute(
                    "INSERT INTO topic_ids (name) VALUES (%s) RETURNING id",
                    (req.name,)
                )
                row = await cur.fetchone()
                if not row:
                    raise HTTPException(status_code=500, detail="Failed to create topic ID")
                topic_id = str(row["id"])
            except Exception as e:
                if "unique constraint" in str(e).lower():
                    raise HTTPException(status_code=409, detail="Topic with this name already exists.")
                raise e
                
    return TopicResponse(topic_id=topic_id)

# --- Analysis Endpoints (Real Implementation) ---

@app.post("/segments/{segment_id}/topics:suggest", response_model=SuggestTopicsResponse)
async def suggest_topics(segment_id: str):
    """
    Analyzes the segment and suggests relevant topics (both existing and new).
    """
    pool = _require_pool()
    
    # 1. Fetch segment text
    segment_row = await _fetch_segment(segment_id)
    segment_text = segment_row["text"]
    
    # 2. Run suggestion pipeline
    try:
        suggestions = await run_suggest_topics(pool, segment_text)
        
        # Map domain model to API model
        api_suggestions = [
            TopicSuggestion(
                topic_id=s.topic_id,
                name=s.name,
                source=s.source,
                description=s.description,
                user_hypothesis=s.user_hypothesis,
                summary_text=s.summary_text
            )
            for s in suggestions
        ]
        
        return SuggestTopicsResponse(suggestions=api_suggestions)
        
    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate topic suggestions.")


@app.post("/analysis:check_hypothesis", response_model=CheckHypothesisResponse)
async def check_hypothesis(req: CheckHypothesisRequest):
    """
    Runs a focused analysis to check if the segment confirms or refutes the user hypothesis.
    """
    try:
        analysis_text = await run_check_hypothesis(
            segment_text=req.segment_text,
            topic_name=req.topic_name,
            user_hypothesis=req.user_hypothesis
        )
        return CheckHypothesisResponse(analysis_text=analysis_text)
    except Exception as e:
        logger.error(f"Failed to check hypothesis: {e}")
        raise HTTPException(status_code=500, detail="Failed to run hypothesis check.")


@app.post("/analysis:generate_pov", response_model=GeneratePovResponse)
async def generate_analyst_pov(req: GeneratePovRequest):
    """
    Generates an analyst POV for a given segment and unsaved topic text.
    Saves a 'draft' record of the run and returns the summary.
    """
    # Placeholder for actual analysis pipeline
    print(f"Generating POV for segment {req.segment_id} on topic '{req.topic_name}'")
    
    pov_summary = f"This is the analyst's take on '{req.topic_name}'. Based on the segment, the hypothesis '{req.user_hypothesis}' seems plausible because..."
    trace_data = {"steps": ["step1_result", "step2_result"], "confidence": 0.9}
    
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO persona_topic_povs (persona, pov_summary, trace_data, run_status)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                ("Analyst Persona", pov_summary, Json(trace_data), "draft")
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="Failed to create POV record.")
            
            return GeneratePovResponse(pov_summary=pov_summary, pov_id=str(row["id"]))


@app.post("/segments/{segment_id}/topics", status_code=204)
async def save_segment_topics_history(segment_id: str, req: SaveTopicsHistoryRequest):
    """
    Saves the final, edited topic analysis for a segment.
    Creates new records in topics_history and links any generated POVs.
    """
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            for topic_payload in req.topics:
                topic_id = topic_payload.topic_id
                
                # If topic_id is null, it's a new topic. Create or find existing by name.
                if not topic_id:
                    async with conn.cursor(row_factory=dict_row) as cur:
                        # Use INSERT ... ON CONFLICT to handle existing topics
                        await cur.execute(
                            """
                            INSERT INTO topic_ids (name) VALUES (%s)
                            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                            RETURNING id;
                            """,
                            (topic_payload.name,)
                        )
                        row = await cur.fetchone()
                        if not row:
                            raise HTTPException(status_code=500, detail="Failed to create or find topic ID.")
                        topic_id = str(row["id"])

                # Now, insert the new entry into the history log.
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        """
                        INSERT INTO topics_history (topic_id, segment_id, name, description, user_hypothesis, summary_text)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id;
                        """,
                        (topic_id, segment_id, topic_payload.name, topic_payload.description, topic_payload.user_hypothesis, topic_payload.summary_text)
                    )
                    history_row = await cur.fetchone()
                    if not history_row:
                        raise HTTPException(status_code=500, detail="Failed to create topics history record.")
                    history_id = str(history_row["id"])

                # If a POV was generated, link it to the new history record and finalize it.
                if topic_payload.pov_id:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            """
                            UPDATE persona_topic_povs
                            SET topics_history_id = %s, run_status = 'final', updated_at = now()
                            WHERE id = %s;
                            """,
                            (history_id, topic_payload.pov_id)
                        )
    return


# --- Documents & Sources Endpoints ---

@app.get("/documents", response_model=List[DocumentList])
async def list_documents():
    """List all non-archived documents with source metadata and segment counts."""
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    d.id,
                    s.name as source_title,
                    d.title,
                    d.author,
                    d.published_at,
                    d.created_at,
                    left(d.content_text, 300) as content_text_preview,
                    d.original_url,
                    COALESCE(seg_counts.segment_count, 0) as segment_count
                FROM documents d
                LEFT JOIN sources s ON d.source_id = s.id
                LEFT JOIN (
                    SELECT document_id, COUNT(*) as segment_count
                    FROM segments
                    GROUP BY document_id
                ) seg_counts ON d.id = seg_counts.document_id
                WHERE d.is_archived = FALSE
                ORDER BY d.created_at DESC
                """
            )
            rows = await cur.fetchall()
            
    results = []
    for r in rows:
        d = dict(r)
        d['id'] = str(d['id'])  # Convert UUID to string
        results.append(DocumentList(**d))
    return results


@app.patch("/documents/{document_id}/archive", status_code=200)
async def archive_document(document_id: str):
    """Archive a document (soft delete - hides from UI but keeps in database)."""
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE documents SET is_archived = TRUE WHERE id = %s RETURNING id",
                (document_id,)
            )
            result = await cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "archived", "document_id": document_id}

@app.get("/sources", response_model=List[SourceList])
async def list_sources():
    """List all sources."""
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    name,
                    type,
                    feed_url as url,
                    created_at
                FROM sources
                ORDER BY created_at DESC
                """
            )
            rows = await cur.fetchall()
            
    results = []
    for r in rows:
        d = dict(r)
        d['id'] = str(d['id'])  # Convert UUID to string
        d['last_polled'] = None  # Not in schema yet
        results.append(SourceList(**d))
        
    return results

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
