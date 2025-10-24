#!/usr/bin/env python3
"""Queue segment generation requests for selected documents."""

from __future__ import annotations

import argparse
import json
import os
from typing import Sequence

import psycopg


def insert_requests(
    conn: psycopg.Connection,
    *,
    document_ids: Sequence[str],
    created_by: str | None,
    options: dict | None,
) -> list[str]:
    options_json = options or {}
    inserted: list[str] = []
    with conn.cursor() as cur:
        for document_id in document_ids:
            cur.execute(
                """
                INSERT INTO segment_generation_requests (document_id, created_by, options)
                SELECT %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM segment_generation_requests
                    WHERE document_id = %s AND status = 'pending'
                )
                RETURNING id
                """,
                (document_id, created_by, json.dumps(options_json), document_id),
            )
            row = cur.fetchone()
            if row:
                inserted.append(row[0])
                cur.execute(
                    """
                    UPDATE documents
                    SET segment_status = 'queued',
                        segment_updated_at = now()
                    WHERE id = %s
                    """,
                    (document_id,),
                )
    conn.commit()
    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Queue segment generation requests")
    parser.add_argument(
        "document_ids",
        nargs="+",
        help="One or more document UUIDs",
    )
    parser.add_argument(
        "--created-by",
        help="Optional identifier of the user queuing the request",
    )
    parser.add_argument(
        "--options",
        help="JSON string with segmentation options (max_chars, etc.)",
    )
    parser.add_argument(
        "--dsn",
        help="Database DSN; defaults to SUPABASE_DB_URL",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dsn = args.dsn or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        raise SystemExit("Database DSN must be provided via --dsn or SUPABASE_DB_URL")

    options = json.loads(args.options) if args.options else None

    with psycopg.connect(dsn, autocommit=False) as conn:
        request_ids = insert_requests(
            conn,
            document_ids=args.document_ids,
            created_by=args.created_by,
            options=options,
        )
    for request_id in request_ids:
        print(f"Queued segment request {request_id}")


if __name__ == "__main__":
    main()
