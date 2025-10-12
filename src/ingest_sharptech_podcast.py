"""Ingest Sharp Tech podcast RSS feed into documents."""

from __future__ import annotations

import calendar
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import feedparser
import psycopg
from psycopg.types.json import Json


@dataclass
class PodcastEntry:
    id: str
    link: str
    title: str
    author: str | None
    published_at: datetime | None
    summary: str | None
    duration: str | None
    content_html: str | None
    enclosure: dict[str, Any] | None
    provenance: dict[str, Any]

    def to_assets(self) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        if self.enclosure:
            assets.append(
                {
                    "type": "audio",
                    "url": self.enclosure.get("href"),
                    "length": self.enclosure.get("length"),
                    "mime_type": self.enclosure.get("type"),
                    "duration": self.duration,
                }
            )
        return assets

    def to_content_text(self) -> str | None:
        if self.summary:
            return self.summary.strip()
        return None


def parse_feed(feed_url: str, months: int = 6) -> Iterable[PodcastEntry]:
    parsed = feedparser.parse(feed_url)
    if parsed.bozo:
        raise RuntimeError(f"Feed parse error: {parsed.bozo_exception}")

    cutoff = datetime.now(timezone.utc) - timedelta(days=30 * months)

    for entry in parsed.entries:
        content_list = entry.get("content", [])
        content_html = content_list[0].get("value") if content_list else None
        enclosure = None
        for link in entry.get("links", []):
            if link.get("rel") == "enclosure":
                enclosure = link
                break
        published = None
        published_struct = entry.get("published_parsed")
        if published_struct:
            published = datetime.fromtimestamp(
                calendar.timegm(published_struct), tz=timezone.utc
            )
            if published < cutoff:
                continue
        provenance = {
            key: entry.get(key)
            for key in entry.keys()
            if key.startswith("atomic_") or key.startswith("itunes_")
        }
        yield PodcastEntry(
            id=str(entry.get("id")),
            link=str(entry.get("link")),
            title=str(entry.get("title")),
            author=entry.get("author"),
            published_at=published,
            summary=entry.get("summary"),
            duration=entry.get("itunes_duration"),
            content_html=content_html,
            enclosure=enclosure,
            provenance=provenance,
        )


def upsert_documents(conn: psycopg.Connection, source_id: str, entries: Iterable[PodcastEntry]) -> None:
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
                    assets,
                    provenance,
                    transcript_status
                )
                VALUES (
                    %(source_id)s,
                    %(external_id)s,
                    'feed_pull',
                    'podcast_audio',
                    %(original_url)s,
                    %(title)s,
                    %(author)s,
                    %(published_at)s,
                    now(),
                    %(content_html)s,
                    %(content_text)s,
                    'pending_transcript',
                    %(assets)s,
                    %(provenance)s,
                    'pending'
                )
                ON CONFLICT (source_id, external_id)
                DO UPDATE SET
                    original_url = EXCLUDED.original_url,
                    title = EXCLUDED.title,
                    author = EXCLUDED.author,
                    published_at = EXCLUDED.published_at,
                    content_html = EXCLUDED.content_html,
                    content_text = EXCLUDED.content_text,
                    assets = EXCLUDED.assets,
                    provenance = EXCLUDED.provenance,
                    ingest_status = EXCLUDED.ingest_status,
                    transcript_status = EXCLUDED.transcript_status,
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
                    "content_text": entry.to_content_text(),
                    "assets": Json(entry.to_assets()),
                    "provenance": Json(entry.provenance),
                },
            )
        conn.commit()


def main() -> None:
    db_url = os.environ.get("SUPABASE_DB_URL")
    feed_url = os.environ.get("SHARPTECH_PODCAST_FEED_URL")
    if not db_url or not feed_url:
        raise SystemExit("SUPABASE_DB_URL and SHARPTECH_PODCAST_FEED_URL must be set")

    months = int(os.environ.get("SHARPTECH_PODCAST_MONTHS", "6"))

    with psycopg.connect(db_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM sources WHERE name=%s", ("Sharp Tech Podcast",))
            row = cur.fetchone()
            if not row:
                raise SystemExit("Sharp Tech Podcast source not found in database")
            source_id = row[0]

        entries = list(parse_feed(feed_url, months=months))
        upsert_documents(conn, source_id, entries)


if __name__ == "__main__":
    main()
