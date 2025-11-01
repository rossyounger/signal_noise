from __future__ import annotations

import os
from typing import Any

import psycopg

from src.ingest_sharptech_podcast import parse_feed as parse_podcast_feed
from src.ingest_sharptech_podcast import upsert_documents as upsert_podcast_documents
from src.ingest_stratechery import parse_feed as parse_article_feed
from src.ingest_stratechery import upsert_documents as upsert_article_documents


def get_source(conn: psycopg.Connection, source_id: str) -> dict[str, Any]:
    """Fetch source details from the database."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, type, feed_url FROM sources WHERE id = %s", (source_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Source {source_id} not found")
        keys = ["id", "name", "type", "feed_url"]
        return dict(zip(keys, row, strict=True))


def run_source_ingestion(db_url: str, source_id: str) -> None:
    """Run the ingestion process for a single source."""
    with psycopg.connect(db_url, autocommit=False) as conn:
        source = get_source(conn, source_id)
        source_type = source.get("type")
        feed_url = source.get("feed_url")

        if not feed_url:
            raise ValueError(f"Source {source_id} has no feed_url.")

        print(f"Ingesting {source['name']} ({source_type})...")

        if source_type == "rss":  # <-- THE FIX IS HERE
            entries = list(parse_article_feed(feed_url))
            upsert_article_documents(conn, source_id, entries)
        elif source_type == "podcast":
            entries = list(parse_podcast_feed(feed_url))
            upsert_podcast_documents(conn, source_id, entries)
        else:
            raise NotImplementedError(f"No ingestion logic for source type: {source_type}")

        conn.commit()
    print(f"Finished ingesting {source['name']}.")