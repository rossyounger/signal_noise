"""Segment generation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from .chunker import split_into_chunks
from .llm_regrouper import SegmentSuggestion, regroup_chunks


@dataclass
class SegmentDraft:
    document_id: str
    text: str
    provenance: dict
    version: int
    content_html: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    status: str = "proposed"
    offset_kind: str = "text"


@dataclass
class SegmentResult:
    document_id: str
    inserted_count: int
    version: int


def generate_segments_for_document(
    conn: psycopg.Connection,
    document_id: str,
    options: dict | None = None,
) -> SegmentResult:
    options = options or {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT content_text,
                   assets,
                   provenance,
                   segment_status,
                   segment_version
            FROM documents
            WHERE id = %s
            """,
            (document_id,),
        )
        record = cur.fetchone()
        if record is None:
            raise ValueError(f"Document {document_id} not found")
    content_text = record["content_text"] or ""
    assets = record.get("assets") or []

    text_source = _select_text_source(content_text, assets, options)
    if not text_source:
        raise ValueError("No text source available for segmentation")

    chunks = split_into_chunks(
        text_source,
        max_chars=options.get("max_chars", 1200),
        min_chars=options.get("min_chars", 400),
        overlap_chars=options.get("overlap_chars", 150),
    )

    next_version = _next_version(conn, document_id)
    llm_client = options.get("llm_client")

    if llm_client:
        suggestions = list(
            regroup_chunks(
                chunk_texts=[chunk.text for chunk in chunks],
                llm_client=llm_client,
                system_prompt=options.get("system_prompt", _DEFAULT_SYSTEM_PROMPT),
                user_prompt_template=options.get(
                    "user_prompt_template", _DEFAULT_USER_PROMPT
                ),
            )
        )
        drafts = list(
            _merge_suggestions(chunks, suggestions, document_id, next_version)
        )
    else:
        drafts = [
            SegmentDraft(
                document_id=document_id,
                text=chunk.text,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                provenance={
                    "chunk_index": chunk.index,
                    "chunk_start": chunk.start_offset,
                    "chunk_end": chunk.end_offset,
                },
                version=next_version,
            )
            for chunk in chunks
        ]

    if not drafts:
        raise ValueError("Segmentation produced no segments")

    _supersede_existing(conn, document_id)
    inserted_count = _persist_segments(conn, drafts)
    _update_document_segment_state(conn, document_id, next_version, "generated")

    return SegmentResult(
        document_id=document_id,
        inserted_count=inserted_count,
        version=next_version,
    )


_DEFAULT_SYSTEM_PROMPT = (
    "You are an analyst splitting long-form research content into precise,\n"
    "fact-preserving snippets. Focus on factual statements and avoid repetition."
)

_DEFAULT_USER_PROMPT = (
    "You are given extracted excerpts from a document. Combine overlapping\n"
    "chunks into 2-5 coherent snippets with accurate start/end markers.\n"
    "If a chunk should stand alone, keep it unchanged.\n\n"
    "Snippets:\n{snippets}"
)


def _select_text_source(content_text: str, assets: Sequence, options: dict) -> str:
    if options.get("prefer_transcript"):
        transcript = _latest_transcript(assets)
        if transcript:
            return transcript
    if content_text:
        return content_text
    return _latest_transcript(assets)


def _latest_transcript(assets: Sequence) -> str:
    for asset in reversed(list(assets)):
        if isinstance(asset, dict) and asset.get("type") == "transcript":
            text = asset.get("text")
            if text:
                return text
    return ""


def _merge_suggestions(
    chunks: Sequence,
    suggestions: Sequence[SegmentSuggestion],
    document_id: str,
    version: int,
) -> Iterable[SegmentDraft]:
    chunk_indices = [getattr(chunk, "index", idx) for idx, chunk in enumerate(chunks)]

    for idx, suggestion in enumerate(suggestions):
        provenance = {
            "suggestion_index": idx,
            "source_chunks": chunk_indices,
            "llm": True,
        }
        yield SegmentDraft(
            document_id=document_id,
            text=suggestion.text,
            start_offset=None,
            end_offset=None,
            provenance=provenance,
            version=version,
        )


def _next_version(conn: psycopg.Connection, document_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) FROM segments WHERE document_id = %s",
            (document_id,),
        )
        current = cur.fetchone()[0]
    return current + 1


def _supersede_existing(conn: psycopg.Connection, document_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE segments
            SET segment_status = 'superseded'
            WHERE document_id = %s
              AND segment_status IN ('proposed', 'final')
            """,
            (document_id,),
        )


def _persist_segments(conn: psycopg.Connection, drafts: Sequence[SegmentDraft]) -> int:
    if not drafts:
        return 0
    values = [
        (
            draft.document_id,
            draft.text,
            draft.content_html,
            draft.start_offset,
            draft.end_offset,
            draft.status,
            draft.version,
            Json(draft.provenance),
            draft.offset_kind,
        )
        for draft in drafts
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO segments (
                document_id,
                text,
                content_html,
                start_offset,
                end_offset,
                segment_status,
                version,
                provenance,
                offset_kind
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            values,
        )
    return len(values)


def _update_document_segment_state(
    conn: psycopg.Connection,
    document_id: str,
    version: int,
    status: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE documents
            SET segment_status = %s,
                segment_version = %s,
                segment_updated_at = now()
            WHERE id = %s
            """,
            (status, version, document_id),
        )
