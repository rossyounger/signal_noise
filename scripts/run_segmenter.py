#!/usr/bin/env python3
"""Process queued segment generation requests."""

from __future__ import annotations

import argparse
import logging
import os
import time
from contextlib import contextmanager
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from segments import SegmentResult, generate_segments_for_document

logger = logging.getLogger(__name__)


@contextmanager
def db_connection(dsn: str | None):
    dsn = dsn or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        raise SystemExit("Database DSN must be provided via --dsn or SUPABASE_DB_URL")
    with psycopg.connect(dsn, autocommit=False) as conn:
        yield conn


def fetch_next_request(
    conn: psycopg.Connection,
    *,
    document_id: Optional[str] = None,
) -> dict | None:
    base_query = """
        SELECT id, document_id, options
        FROM segment_generation_requests
        WHERE status = 'pending'
    """
    params: dict[str, str] = {}
    if document_id:
        base_query += " AND document_id = %(document_id)s"
        params["document_id"] = document_id
    base_query += " ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(base_query, params)
        row = cur.fetchone()
        if not row:
            return None
        cur.execute(
            "UPDATE segment_generation_requests SET status = 'running' WHERE id = %s",
            (row["id"],),
        )
    conn.commit()
    return dict(row)


def mark_request(
    conn: psycopg.Connection,
    *,
    request_id: str,
    status: str,
    error: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE segment_generation_requests
            SET status = %s,
                error = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (status, error, request_id),
        )
    conn.commit()


def mark_document_status(
    conn: psycopg.Connection,
    *,
    document_id: str,
    status: str,
    version: int | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE documents
            SET segment_status = %s,
                segment_version = COALESCE(%s, segment_version),
                segment_updated_at = now()
            WHERE id = %s
            """,
            (status, version, document_id),
        )
    conn.commit()


def process_request(
    conn: psycopg.Connection,
    *,
    request_id: str,
    document_id: str,
    options: dict,
) -> SegmentResult | None:
    try:
        mark_document_status(conn, document_id=document_id, status="running")
        logger.info("Generating segments for document %s (request %s)", document_id, request_id)
        result = generate_segments_for_document(conn, document_id, options)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Segmentation failed for document %s", document_id)
        mark_request(conn, request_id=request_id, status="failed", error=str(exc))
        mark_document_status(conn, document_id=document_id, status="failed")
        conn.rollback()
        return None

    mark_request(conn, request_id=request_id, status="done")
    mark_document_status(
        conn,
        document_id=document_id,
        status="generated",
        version=result.version,
    )
    logger.info(
        "Inserted %s segments for document %s (version %s)",
        result.inserted_count,
        document_id,
        result.version,
    )
    return result


def run_once(conn: psycopg.Connection, document_id: str | None = None) -> bool:
    request = fetch_next_request(conn, document_id=document_id)
    if not request:
        return False

    process_request(
        conn,
        request_id=request["id"],
        document_id=request["document_id"],
        options=request.get("options") or {},
    )
    return True


def run_loop(
    conn: psycopg.Connection,
    *,
    document_id: str | None,
    poll_interval: float,
) -> None:
    while True:
        has_work = run_once(conn, document_id=document_id)
        if not has_work:
            time.sleep(poll_interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process segment generation queue")
    parser.add_argument(
        "--dsn",
        help="Database connection string; defaults to SUPABASE_DB_URL env var",
    )
    parser.add_argument(
        "--document-id",
        help="Only process requests for a specific document",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process a single request and exit",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds to sleep between polls in continuous mode",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    with db_connection(args.dsn) as conn:
        if args.once:
            worked = run_once(conn, document_id=args.document_id)
            if not worked:
                logger.info("No pending requests")
        else:
            run_loop(conn, document_id=args.document_id, poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
