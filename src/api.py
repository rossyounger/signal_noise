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
from src.analysis.suggestions import suggest_hypotheses as run_suggest_hypotheses, HypothesisSuggestionModel
from src.analysis.hypothesis import check_hypothesis as run_check_hypothesis
from src.analysis.reference_fetcher import (
    fetch_reference_content, 
    get_cached_reference, 
    cache_reference_content
)

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


# --- Data Models (Hypothesis-Centric Architecture) ---

class HypothesisView(BaseModel):
    """Represents a hypothesis for the home page view."""
    hypothesis_id: str
    hypothesis_text: str | None
    description: str | None
    reference_url: str | None
    reference_type: str | None
    last_updated_at: datetime
    evidence_count: int
    latest_segment_id: str | None
    latest_segment_text_preview: str | None
    latest_document_id: str | None
    latest_document_title: str | None


class HypothesisEvidenceEntry(BaseModel):
    """Represents a single evidence entry for a hypothesis."""
    evidence_id: str
    hypothesis_id: str
    segment_id: str
    verdict: str | None
    analysis_text: str | None
    authored_by: str
    created_at: datetime
    segment_text_preview: str | None
    document_id: str | None
    document_title: str | None


class SegmentHypothesis(BaseModel):
    """Represents a hypothesis linked to a specific segment."""
    hypothesis_id: str
    hypothesis_text: str | None
    description: str | None
    reference_url: str | None
    reference_type: str | None
    verdict: str | None
    analysis_text: str | None
    created_at: datetime


class HypothesisCreate(BaseModel):
    hypothesis_text: str
    description: str | None = None
    reference_url: str | None = None
    reference_type: str | None = None


class HypothesisResponse(BaseModel):
    hypothesis_id: str


class HypothesisSuggestion(BaseModel):
    hypothesis_id: str | None = None
    hypothesis_text: str
    source: str  # 'existing' | 'generated'
    description: str | None = None
    analysis_text: str | None = None  # Pre-filled analysis if available


class SuggestHypothesesResponse(BaseModel):
    suggestions: List[HypothesisSuggestion]


class EvidencePayload(BaseModel):
    hypothesis_id: str | None  # null if it's a new hypothesis
    hypothesis_text: str
    description: str | None
    verdict: str | None = None  # 'confirms', 'refutes', 'nuances', 'irrelevant'
    analysis_text: str | None = None
    pov_id: str | None = None  # The ID of the draft POV run, if one was generated


class SaveEvidenceRequest(BaseModel):
    evidence: List[EvidencePayload]


class GeneratePovRequest(BaseModel):
    segment_id: str
    hypothesis_text: str
    description: str | None


class GeneratePovResponse(BaseModel):
    pov_summary: str
    pov_id: str  # The ID of the draft record in persona_topic_povs


class CheckHypothesisRequest(BaseModel):
    segment_text: str
    hypothesis_text: str
    hypothesis_description: str | None = None
    reference_url: str | None = None
    include_full_reference: bool = False
    hypothesis_id: str | None = None


class CheckHypothesisResponse(BaseModel):
    analysis_text: str


class HypothesisReferenceResponse(BaseModel):
    hypothesis_id: str
    reference_url: str | None
    reference_type: str | None
    full_text: str | None
    character_count: int | None
    cached: bool


# --- Questions Models (P2 Feature) ---

class Question(BaseModel):
    question_id: str
    question_text: str
    created_at: datetime
    hypothesis_count: int


class QuestionCreate(BaseModel):
    question_text: str


class QuestionResponse(BaseModel):
    question_id: str


class QuestionHypothesisLink(BaseModel):
    hypothesis_id: str


class QuestionHypothesis(BaseModel):
    """Represents a hypothesis linked to a question."""
    hypothesis_id: str
    hypothesis_text: str | None
    description: str | None
    reference_url: str | None
    reference_type: str | None
    evidence_count: int
    created_at: datetime


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


# --- Ingestion & Transcription Workflow ---

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


@app.delete("/segments/{segment_id}", status_code=200)
async def delete_segment(segment_id: str):
    """Delete a segment."""
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM segments WHERE id = %s RETURNING id",
                (segment_id,)
            )
            result = await cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Segment not found")
    return {"status": "deleted", "segment_id": segment_id}


# --- Manual Segmentation Workflow ---

class IngestUrlRequest(BaseModel):
    url: str


class IngestUrlResponse(BaseModel):
    document_id: str
    status: str


@app.post("/documents/ingest-url", response_model=IngestUrlResponse)
async def ingest_document_from_url(req: IngestUrlRequest):
    """
    Manually ingest a document from a URL.
    Fetches the page, extracts content/metadata, and saves to DB.
    """
    import requests
    from bs4 import BeautifulSoup
    from datetime import datetime
    import email.utils

    logger.info(f"Ingesting URL: {req.url}")

    try:
        # 1. Fetch the page
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SignalNoiseIngest/1.0; +https://signal-noise)"
        }
        response = requests.get(req.url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")

        # 2. Extract Metadata
        # -- Title --
        title = None
        if soup.find("meta", property="og:title"):
            title = soup.find("meta", property="og:title")["content"]
        elif soup.title:
            title = soup.title.string
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        
        # -- Author --
        author = None
        if soup.find("meta", attrs={"name": "author"}):
            author = soup.find("meta", attrs={"name": "author"})["content"]
        elif soup.find("meta", property="article:author"):
            author = soup.find("meta", property="article:author")["content"]
        elif soup.find("a", attrs={"rel": "author"}):
            author = soup.find("a", attrs={"rel": "author"}).get_text(strip=True)

        # -- Date --
        published_at = None
        date_str = None
        if soup.find("meta", property="article:published_time"):
            date_str = soup.find("meta", property="article:published_time")["content"]
        elif soup.find("meta", attrs={"name": "date"}):
            date_str = soup.find("meta", attrs={"name": "date"})["content"]
        elif soup.find("time", attrs={"datetime": True}):
            date_str = soup.find("time", attrs={"datetime": True})["datetime"]

        if date_str:
            try:
                # Try ISO format first (common in meta tags)
                published_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                try:
                    # Try RFC 2822 (common in headers/older meta)
                    parsed = email.utils.parsedate_to_datetime(date_str)
                    if parsed:
                        published_at = parsed
                except Exception as e:
                    logger.warning(f"Failed to parse date '{date_str}': {e}")


        # 3. Extract Content (Basic Strategy)
        # Try to find the semantic 'main' content to avoid nav/footer garbage
        content_elem = soup.find("article") or soup.find("main") or soup.body

        # Remove script/style tags
        if content_elem:
            for script in content_elem(["script", "style", "nav", "footer"]):
                script.decompose()
            
            content_html = str(content_elem)
            content_text = content_elem.get_text("\n", strip=True)
        else:
            # Fallback to raw text if no body (unlikely for HTML)
            content_html = response.text
            content_text = soup.get_text("\n", strip=True)

        # 4. Save to DB
        pool = _require_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO documents (
                        source_id,
                        external_id,
                        ingest_method,
                        original_media_type,
                        original_url,
                        title,
                        author,
                        published_at,
                        ingested_at,
                        content_html,
                        content_text,
                        ingest_status
                    )
                    VALUES (
                        NULL, -- No source_id for direct URL
                        %s, -- Use URL as external_id
                        'direct_url',
                        'article',
                        %s,
                        %s,
                        %s,
                        %s,
                        now(),
                        %s,
                        %s,
                        'ok'
                    )
                    RETURNING id
                    """,
                    (
                        req.url,
                        req.url,
                        title or "Untitled Document",
                        author,
                        published_at,
                        content_html,
                        content_text
                    )
                )
                row = await cur.fetchone()
                if not row:
                    raise HTTPException(status_code=500, detail="Failed to insert document.")
                
                doc_id = str(row[0])
                logger.info(f"Successfully ingested document {doc_id}")
                return IngestUrlResponse(document_id=doc_id, status="ok")

    except Exception as e:
        logger.error(f"Failed to ingest URL {req.url}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class Segment(BaseModel):
    id: str
    document_id: str
    title: str
    author: str | None = None
    text: str
    created_at: datetime
    published_at: datetime | None = None
    hypothesis_count: int = 0


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
    """List all segments, joining with documents to get metadata and hypothesis counts."""
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
                    d.published_at,
                    COALESCE(hyp_counts.hypothesis_count, 0) as hypothesis_count
                FROM segments s
                JOIN documents d ON s.document_id = d.id
                LEFT JOIN (
                    SELECT 
                        segment_id,
                        COUNT(DISTINCT hypothesis_id) as hypothesis_count
                    FROM hypothesis_evidence
                    GROUP BY segment_id
                ) hyp_counts ON s.id = hyp_counts.segment_id
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


# --- Hypothesis & Evidence Workflow (New Architecture) ---

@app.get("/segments/{segment_id}/hypotheses", response_model=List[SegmentHypothesis])
async def get_segment_hypotheses(segment_id: str):
    """
    Get all hypotheses linked to a specific segment via hypothesis_evidence.
    Returns the hypothesis details along with the evidence verdict/analysis for this segment.
    """
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    h.id as hypothesis_id,
                    h.hypothesis_text,
                    h.description,
                    h.reference_url,
                    h.reference_type,
                    he.verdict,
                    he.analysis_text,
                    he.created_at
                FROM hypothesis_evidence he
                JOIN hypotheses h ON he.hypothesis_id = h.id
                WHERE he.segment_id = %s
                ORDER BY he.created_at DESC
                """,
                (segment_id,)
            )
            rows = await cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d['hypothesis_id'] = str(d['hypothesis_id'])
        results.append(SegmentHypothesis(**d))
    return results


@app.get("/hypotheses", response_model=List[HypothesisView])
async def list_hypotheses():
    """
    Lists all hypotheses with their latest evidence summary.
    """
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                WITH evidence_stats AS (
                    SELECT
                        hypothesis_id,
                        COUNT(*) as evidence_count,
                        MAX(created_at) as latest_evidence_at
                    FROM hypothesis_evidence
                    GROUP BY hypothesis_id
                ),
                latest_evidence AS (
                    SELECT DISTINCT ON (hypothesis_id)
                        hypothesis_id,
                        segment_id,
                        created_at
                    FROM hypothesis_evidence
                    ORDER BY hypothesis_id, created_at DESC
                )
                SELECT
                    h.id as hypothesis_id,
                    h.hypothesis_text,
                    h.description,
                    h.reference_url,
                    h.reference_type,
                    COALESCE(es.latest_evidence_at, h.updated_at) as last_updated_at,
                    COALESCE(es.evidence_count, 0) as evidence_count,
                    le.segment_id as latest_segment_id,
                    LEFT(s.text, 200) as latest_segment_text_preview,
                    d.id as latest_document_id,
                    d.title as latest_document_title
                FROM hypotheses h
                LEFT JOIN evidence_stats es ON h.id = es.hypothesis_id
                LEFT JOIN latest_evidence le ON h.id = le.hypothesis_id
                LEFT JOIN segments s ON le.segment_id = s.id
                LEFT JOIN documents d ON s.document_id = d.id
                ORDER BY last_updated_at DESC
                """
            )
            rows = await cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d['hypothesis_id'] = str(d['hypothesis_id'])
        if d.get('latest_segment_id'):
            d['latest_segment_id'] = str(d['latest_segment_id'])
        if d.get('latest_document_id'):
            d['latest_document_id'] = str(d['latest_document_id'])
        results.append(HypothesisView(**d))
    return results


@app.post("/hypotheses", status_code=201)
async def create_hypothesis(req: HypothesisCreate) -> HypothesisResponse:
    """
    Creates a new hypothesis manually.
    """
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO hypotheses (hypothesis_text, description, reference_url, reference_type)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (req.hypothesis_text, req.description, req.reference_url, req.reference_type)
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="Failed to create hypothesis")
            hypothesis_id = str(row["id"])
                
    return HypothesisResponse(hypothesis_id=hypothesis_id)


@app.delete("/hypotheses/{hypothesis_id}", status_code=200)
async def delete_hypothesis(hypothesis_id: str):
    """
    Delete a hypothesis and all related evidence (CASCADE).
    """
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM hypotheses WHERE id = %s RETURNING id",
                (hypothesis_id,)
            )
            result = await cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Hypothesis not found")
    return {"status": "deleted", "hypothesis_id": hypothesis_id}


@app.get("/hypotheses/{hypothesis_id}/evidence", response_model=List[HypothesisEvidenceEntry])
async def get_hypothesis_evidence(hypothesis_id: str):
    """
    Returns all evidence entries for a given hypothesis, sorted by created_at DESC.
    Each entry represents one segment linked to this hypothesis with a verdict.
    """
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    he.id as evidence_id,
                    he.hypothesis_id,
                    he.segment_id,
                    he.verdict,
                    he.analysis_text,
                    he.authored_by,
                    he.created_at,
                    LEFT(s.text, 200) as segment_text_preview,
                    d.id as document_id,
                    d.title as document_title
                FROM hypothesis_evidence he
                LEFT JOIN segments s ON he.segment_id = s.id
                LEFT JOIN documents d ON s.document_id = d.id
                WHERE he.hypothesis_id = %s
                ORDER BY he.created_at DESC
                """,
                (hypothesis_id,)
            )
            rows = await cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d['evidence_id'] = str(d['evidence_id'])
        d['hypothesis_id'] = str(d['hypothesis_id'])
        d['segment_id'] = str(d['segment_id'])
        if d.get('document_id'):
            d['document_id'] = str(d['document_id'])
        results.append(HypothesisEvidenceEntry(**d))
    return results


@app.get("/hypotheses/{hypothesis_id}/reference", response_model=HypothesisReferenceResponse)
async def get_hypothesis_reference(hypothesis_id: str):
    """
    Fetches the full reference document for a hypothesis.
    Returns cached content if available, otherwise fetches from URL.
    """
    pool = _require_pool()
    
    # 1. Get hypothesis with reference URL
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT reference_url, reference_type FROM hypotheses WHERE id = %s",
                (hypothesis_id,)
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Hypothesis not found")
            
            reference_url = row.get('reference_url')
            reference_type = row.get('reference_type')
            
            if not reference_url:
                return HypothesisReferenceResponse(
                    hypothesis_id=hypothesis_id,
                    reference_url=None,
                    reference_type=None,
                    full_text=None,
                    character_count=None,
                    cached=False
                )
    
    # 2. Check cache first
    full_text = await get_cached_reference(hypothesis_id, pool)
    cached = full_text is not None
    
    # 3. Fetch if not cached
    if not full_text:
        full_text = await fetch_reference_content(reference_url)
        
        # Cache the fetched content
        if full_text:
            async with pool.connection() as conn:
                await cache_reference_content(hypothesis_id, full_text, conn)
    
    return HypothesisReferenceResponse(
        hypothesis_id=hypothesis_id,
        reference_url=reference_url,
        reference_type=reference_type,
        full_text=full_text,
        character_count=len(full_text) if full_text else None,
        cached=cached
    )


# --- Analysis Endpoints ---

@app.post("/segments/{segment_id}/hypotheses:suggest", response_model=SuggestHypothesesResponse)
async def suggest_hypotheses(segment_id: str):
    """
    Analyzes the segment and suggests relevant hypotheses (both existing and new).
    """
    pool = _require_pool()
    
    # 1. Fetch segment text
    segment_row = await _fetch_segment(segment_id)
    segment_text = segment_row["text"]
    
    # 2. Run suggestion pipeline
    try:
        suggestions = await run_suggest_hypotheses(pool, segment_text)
        
        # Map domain model to API model
        api_suggestions = [
            HypothesisSuggestion(
                hypothesis_id=s.hypothesis_id,
                hypothesis_text=s.hypothesis_text,
                source=s.source,
                description=s.description,
                analysis_text=s.analysis_text
            )
            for s in suggestions
        ]
        
        return SuggestHypothesesResponse(suggestions=api_suggestions)
        
    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate hypothesis suggestions.")


@app.post("/analysis:check_hypothesis", response_model=CheckHypothesisResponse)
async def check_hypothesis(req: CheckHypothesisRequest):
    """
    Runs a focused analysis to check if the segment confirms or refutes the hypothesis.
    Optionally includes full reference document context if requested.
    """
    pool = _require_pool()
    try:
        analysis_text = await run_check_hypothesis(
            segment_text=req.segment_text,
            hypothesis_text=req.hypothesis_text,
            hypothesis_description=req.hypothesis_description,
            reference_url=req.reference_url,
            include_full_reference=req.include_full_reference,
            hypothesis_id=req.hypothesis_id,
            db_connection=pool
        )
        return CheckHypothesisResponse(analysis_text=analysis_text)
    except Exception as e:
        logger.error(f"Failed to check hypothesis: {e}")
        raise HTTPException(status_code=500, detail="Failed to run hypothesis check.")


@app.post("/analysis:generate_pov", response_model=GeneratePovResponse)
async def generate_analyst_pov(req: GeneratePovRequest):
    """
    Generates an analyst POV for a given segment and hypothesis.
    Saves a 'draft' record of the run and returns the summary.
    """
    # Placeholder for actual analysis pipeline
    print(f"Generating POV for segment {req.segment_id} on hypothesis '{req.hypothesis_text}'")
    
    pov_summary = f"This is the analyst's take on '{req.hypothesis_text}'. Based on the segment, this hypothesis seems plausible because..."
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


@app.post("/segments/{segment_id}/evidence", status_code=204)
async def save_segment_evidence(segment_id: str, req: SaveEvidenceRequest):
    """
    Saves evidence linking a segment to hypotheses.
    Creates new hypothesis_evidence records.
    For new hypotheses (hypothesis_id is null), creates the hypothesis first.
    """
    pool = _require_pool()
    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                for evidence_payload in req.evidence:
                    # Normalize hypothesis_id: treat empty string as None for new hypotheses
                    hypothesis_id = evidence_payload.hypothesis_id if evidence_payload.hypothesis_id else None
                    
                    # If hypothesis_id is null or empty, it's a new hypothesis. Create it first.
                    if not hypothesis_id:
                        async with conn.cursor(row_factory=dict_row) as cur:
                            await cur.execute(
                                """
                                INSERT INTO hypotheses (hypothesis_text, description)
                                VALUES (%s, %s)
                                RETURNING id
                                """,
                                (evidence_payload.hypothesis_text, evidence_payload.description)
                            )
                            row = await cur.fetchone()
                            if not row:
                                raise HTTPException(status_code=500, detail="Failed to create hypothesis.")
                            hypothesis_id = str(row["id"])

                    # Now, insert the evidence record.
                    async with conn.cursor(row_factory=dict_row) as cur:
                        await cur.execute(
                            """
                            INSERT INTO hypothesis_evidence (hypothesis_id, segment_id, verdict, analysis_text)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id;
                            """,
                            (hypothesis_id, segment_id, evidence_payload.verdict, evidence_payload.analysis_text)
                        )
                        evidence_row = await cur.fetchone()
                        if not evidence_row:
                            raise HTTPException(status_code=500, detail="Failed to create evidence record.")
                        evidence_id = str(evidence_row["id"])

                    # If a POV was generated, link it to the evidence record and finalize it.
                    if evidence_payload.pov_id:
                        async with conn.cursor() as cur:
                            await cur.execute(
                                """
                                UPDATE persona_topic_povs
                                SET hypothesis_evidence_id = %s, run_status = 'final', updated_at = now()
                                WHERE id = %s;
                                """,
                                (evidence_id, evidence_payload.pov_id)
                            )
        return
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save segment evidence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save evidence: {str(e)}")


# --- Questions Endpoints (P2 Feature) ---

@app.get("/questions", response_model=List[Question])
async def list_questions():
    """List all questions with hypothesis counts."""
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    q.id as question_id,
                    q.question_text,
                    q.created_at,
                    COALESCE(COUNT(qh.hypothesis_id), 0) as hypothesis_count
                FROM questions q
                LEFT JOIN question_hypotheses qh ON q.id = qh.question_id
                GROUP BY q.id, q.question_text, q.created_at
                ORDER BY q.created_at DESC
                """
            )
            rows = await cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d['question_id'] = str(d['question_id'])
        results.append(Question(**d))
    return results


@app.post("/questions", status_code=201)
async def create_question(req: QuestionCreate) -> QuestionResponse:
    """Create a new question."""
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "INSERT INTO questions (question_text) VALUES (%s) RETURNING id",
                (req.question_text,)
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="Failed to create question")
            question_id = str(row["id"])
    return QuestionResponse(question_id=question_id)


@app.delete("/questions/{question_id}", status_code=200)
async def delete_question(question_id: str):
    """
    Delete a question and all its links to hypotheses (CASCADE).
    Hypotheses themselves are not affected.
    """
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM questions WHERE id = %s RETURNING id",
                (question_id,)
            )
            result = await cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Question not found")
    return {"status": "deleted", "question_id": question_id}


@app.post("/questions/{question_id}/hypotheses", status_code=201)
async def link_hypothesis_to_question(question_id: str, req: QuestionHypothesisLink):
    """Link a hypothesis to a question."""
    pool = _require_pool()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO question_hypotheses (question_id, hypothesis_id)
                    VALUES (%s, %s)
                    ON CONFLICT (question_id, hypothesis_id) DO NOTHING
                    RETURNING id
                    """,
                    (question_id, req.hypothesis_id)
                )
                row = await cur.fetchone()
                # If row is None, it means the link already existed (conflict)
        return {"status": "linked", "question_id": question_id, "hypothesis_id": req.hypothesis_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/questions/{question_id}/hypotheses", response_model=List[QuestionHypothesis])
async def get_question_hypotheses(question_id: str):
    """Get all hypotheses linked to a specific question."""
    pool = _require_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    h.id as hypothesis_id,
                    h.hypothesis_text,
                    h.description,
                    h.reference_url,
                    h.reference_type,
                    h.created_at,
                    COALESCE(ev_counts.evidence_count, 0) as evidence_count
                FROM question_hypotheses qh
                JOIN hypotheses h ON qh.hypothesis_id = h.id
                LEFT JOIN (
                    SELECT hypothesis_id, COUNT(*) as evidence_count
                    FROM hypothesis_evidence
                    GROUP BY hypothesis_id
                ) ev_counts ON h.id = ev_counts.hypothesis_id
                WHERE qh.question_id = %s
                ORDER BY qh.created_at DESC
                """,
                (question_id,)
            )
            rows = await cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d['hypothesis_id'] = str(d['hypothesis_id'])
        results.append(QuestionHypothesis(**d))
    return results


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
                ORDER BY d.published_at DESC NULLS LAST, d.created_at DESC
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


class DocumentUpdate(BaseModel):
    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    source_id: str | None = None


@app.patch("/documents/{document_id}", response_model=DocumentList)
async def update_document_metadata(document_id: str, update: DocumentUpdate):
    """Update document metadata (Title, Author, Published Date, Source)."""
    pool = _require_pool()
    
    # Build dynamic update query
    fields = []
    values = []
    if update.title is not None:
        fields.append("title = %s")
        values.append(update.title)
    if update.author is not None:
        fields.append("author = %s")
        values.append(update.author)
    if update.published_at is not None:
        fields.append("published_at = %s")
        values.append(update.published_at)
    if update.source_id is not None:
        fields.append("source_id = %s")
        values.append(update.source_id if update.source_id else None)
        
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    values.append(document_id)  # For WHERE clause
    
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"""
                UPDATE documents 
                SET {", ".join(fields)}, updated_at = now()
                WHERE id = %s
                RETURNING id
                """,
                values
            )
            req_result = await cur.fetchone()
            if not req_result:
                raise HTTPException(status_code=404, detail="Document not found")

            # Return full document object similar to list_documents
            await cur.execute(
                """
                SELECT
                    d.id,
                    s.name as source_title,
                    d.title,
                    d.author,
                    d.published_at,
                    d.created_at,
                    LEFT(d.content_text, 200) as content_text_preview,
                    d.original_url,
                    COALESCE(seg_counts.segment_count, 0) as segment_count
                FROM documents d
                LEFT JOIN sources s ON d.source_id = s.id
                LEFT JOIN (
                    SELECT document_id, COUNT(*) as segment_count
                    FROM segments
                    GROUP BY document_id
                ) seg_counts ON d.id = seg_counts.document_id
                WHERE d.id = %s
                """,
                (document_id,)
            )
            row = await cur.fetchone()
            d = dict(row)
            d['id'] = str(d['id'])
            return DocumentList(**d)


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
