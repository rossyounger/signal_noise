from __future__ import annotations

import os
from contextlib import asynccontextmanager

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

load_dotenv()

# Database connection pool
db_pool: AsyncConnectionPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL must be set")
    db_pool = AsyncConnectionPool(conninfo=db_url)
    # The await db_pool.open() was removed by the user, so I will respect that.
    yield
    await db_pool.close()


app = FastAPI(lifespan=lifespan)

# Add this middleware to help with running behind a proxy like ngrok
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# --- Ingestion Workflow ---


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
    try:
        async with db_pool.connection() as conn:
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
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(insert_sql, params)
                result = await cur.fetchone()
                request_id = str(result[0]) 
        return TranscriptionResponse(request_id=request_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Manual Segmentation Workflow ---


class DocumentContent(BaseModel):
    document_id: str
    content_text: str


@app.get("/documents/{document_id}/content")
async def get_document_content(document_id: str) -> DocumentContent:
    """Fetch the text content of a document."""
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT content_text FROM documents WHERE id = %s", (document_id,))
            result = await cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Document not found")
            return DocumentContent(document_id=document_id, content_text=result[0])


class SegmentCreate(BaseModel):
    document_id: str
    text: str
    start_offset: int
    end_offset: int


class SegmentResponse(BaseModel):
    segment_id: str


@app.post("/segments", status_code=201)
async def create_manual_segment(req: SegmentCreate) -> SegmentResponse:
    """Create a new segment manually."""
    from psycopg.types.json import Json

    provenance = {"source": "manual"}
    insert_sql = """
        INSERT INTO segments
            (document_id, text, start_offset, end_offset, provenance, segment_status)
        VALUES (%(doc_id)s, %(text)s, %(start)s, %(end)s, %(prov)s, 'raw_text')
        RETURNING id
    """
    params = {
        "doc_id": req.document_id,
        "text": req.text,
        "start": req.start_offset,
        "end": req.end_offset,
        "prov": Json(provenance),
    }
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(insert_sql, params)
                result = await cur.fetchone()
                segment_id = str(result[0])
        return SegmentResponse(segment_id=segment_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
