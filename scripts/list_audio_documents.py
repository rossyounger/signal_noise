"""List audio documents needing transcription."""

from __future__ import annotations

import os
from datetime import datetime

import psycopg


def main() -> None:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise SystemExit("SUPABASE_DB_URL must be set")

    query = """
        SELECT id,
               title,
               published_at,
               transcript_status,
               (assets ->> 0) IS NOT NULL AS has_assets
        FROM documents
        WHERE assets @> '[{"type": "audio"}]'::jsonb
        ORDER BY published_at DESC NULLS LAST
        LIMIT 25
    """

    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    if not rows:
        print("No audio documents found.")
        return

    print("ID                                  | Published           | Status   | Title")
    print("-" * 100)
    for doc_id, title, published_at, status, _ in rows:
        published = (
            published_at.strftime("%Y-%m-%d %H:%M")
            if isinstance(published_at, datetime)
            else "--"
        )
        status = status or "pending"
        print(f"{doc_id} | {published} | {status:8} | {title}")


if __name__ == "__main__":
    main()
