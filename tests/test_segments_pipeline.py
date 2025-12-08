"""Tests for the segments pipeline."""

from __future__ import annotations

import os

import psycopg
import pytest
from pytest import MonkeyPatch

from segments.chunker import split_into_chunks
from segments.pipeline import SegmentResult, generate_segments_for_document

pytestmark = pytest.mark.integration


@pytest.fixture(name="temp_db_conn")
def fixture_temp_db_conn(monkeypatch: MonkeyPatch) -> psycopg.Connection:
    dsn = os.getenv("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip("SUPABASE_DB_URL not configured for integration tests")
    conn = psycopg.connect(dsn, autocommit=False)
    yield conn
    conn.rollback()
    conn.close()


def test_split_into_chunks_respects_bounds():
    text = "Paragraph one." * 100
    chunks = split_into_chunks(text, max_chars=200, min_chars=50, overlap_chars=20)
    assert chunks
    for chunk in chunks:
        assert len(chunk.text) <= 200


def test_generate_segments_smoke(temp_db_conn: psycopg.Connection):
    document_id = "00000000-0000-0000-0000-000000000001"

    with temp_db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (id, ingest_method, content_text, segment_status, segment_version)
            VALUES (%s, 'test', %s, 'not_started', 0)
            ON CONFLICT (id) DO UPDATE
            SET content_text = EXCLUDED.content_text,
                segment_status = EXCLUDED.segment_status,
                segment_version = EXCLUDED.segment_version
            """,
            (document_id, "Sentence one. Sentence two." * 10),
        )
    temp_db_conn.commit()

    result = generate_segments_for_document(
        temp_db_conn,
        document_id,
        options={"max_chars": 100, "min_chars": 40, "overlap_chars": 10},
    )

    assert isinstance(result, SegmentResult)
    assert result.inserted_count > 0

    with temp_db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT segment_status, segment_version
            FROM documents
            WHERE id = %s
            """,
            (document_id,),
        )
        status, version = cur.fetchone()

    assert status == "generated"
    assert version == result.version

    with temp_db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*), bool_and(offset_kind = 'text'), bool_and(content_html IS NULL)
            FROM segments
            WHERE document_id = %s
            """,
            (document_id,),
        )
        count, is_text_offsets, html_all_null = cur.fetchone()

    assert count == result.inserted_count
    assert is_text_offsets
    assert html_all_null
