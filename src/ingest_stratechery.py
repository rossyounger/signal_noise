"""Ingest Stratechery RSS feed into the documents table."""

from __future__ import annotations

import calendar
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import feedparser
import psycopg
from bs4 import BeautifulSoup
from psycopg.types.json import Json


@dataclass
class FeedEntry:
    id: str
    link: str
    title: str
    author: str | None
    published_at: datetime | None
    summary: str | None
    content_html: str
    provenance: dict[str, Any]

    @property
    def content_text(self) -> str:
        soup = BeautifulSoup(self.content_html, "html.parser")
        text = soup.get_text("\n")
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def parse_feed(feed_url: str) -> Iterable[FeedEntry]:
    parsed = feedparser.parse(feed_url)
    if parsed.bozo:
        raise RuntimeError(f"Feed parse error: {parsed.bozo_exception}")

    for entry in parsed.entries:
        content_list = entry.get("content", [])
        if not content_list:
            continue
        content_html = content_list[0].get("value", "")
        provenance = {
            key: entry.get(key)
            for key in entry.keys()
            if key.startswith("atomic_")
        }
        published = None
        published_struct = entry.get("published_parsed")
        if published_struct:
            published = datetime.fromtimestamp(
                calendar.timegm(published_struct), tz=timezone.utc
            )
        yield FeedEntry(
            id=str(entry.get("id")),
            link=str(entry.get("link")),
            title=str(entry.get("title")),
            author=entry.get("author"),
            published_at=published,
            summary=entry.get("summary"),
            content_html=content_html,
            provenance=provenance,
        )


def upsert_documents(conn: psycopg.Connection, source_id: str, entries: Iterable[FeedEntry]) -> None:
    with conn.cursor() as cur:
        for entry in entries:
            cur.execute(
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
                    ingest_status,
                    provenance
                )
                VALUES (
                    %(source_id)s,
                    %(external_id)s,
                    'feed_pull',
                    'article',
                    %(original_url)s,
                    %(title)s,
                    %(author)s,
                    %(published_at)s,
                    now(),
                    %(content_html)s,
                    %(content_text)s,
                    'ok',
                    %(provenance)s
                )
                ON CONFLICT (source_id, external_id)
                DO UPDATE SET
                    original_url = EXCLUDED.original_url,
                    title = EXCLUDED.title,
                    author = EXCLUDED.author,
                    published_at = EXCLUDED.published_at,
                    content_html = EXCLUDED.content_html,
                    content_text = EXCLUDED.content_text,
                    provenance = EXCLUDED.provenance,
                    ingest_status = 'ok',
                    ingest_error = NULL,
                    updated_at = now()
                """,
                {
                    "source_id": source_id,
                    "external_id": entry.id,
                    "original_url": entry.link,
                    "title": entry.title,
                    "author": entry.author,
                    "published_at": entry.published_at,
                    "content_html": entry.content_html,
                    "content_text": entry.content_text,
                    "provenance": Json(entry.provenance),
                },
            )
        conn.commit()


def main() -> None:
    db_url = os.environ.get("SUPABASE_DB_URL")
    feed_url = os.environ.get("STRATECHERY_FEED_URL")
    if not db_url or not feed_url:
        raise SystemExit("SUPABASE_DB_URL and STRATECHERY_FEED_URL must be set")

    with psycopg.connect(db_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM sources WHERE name=%s", ("Stratechery",))
            row = cur.fetchone()
            if not row:
                raise SystemExit("Stratechery source not found in database")
            source_id = row[0]

        entries = list(parse_feed(feed_url))
        upsert_documents(conn, source_id, entries)


if __name__ == "__main__":
    main()
