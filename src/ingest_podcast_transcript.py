"""Ingest a podcast RSS feed and scrape the transcript from the episode's webpage."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import feedparser
import psycopg
import requests
from bs4 import BeautifulSoup
from psycopg.types.json import Json


@dataclass
class PodcastTranscriptEntry:
    id: str
    link: str
    title: str
    author: str | None
    published_at: datetime | None
    summary: str | None
    content_text: str | None
    provenance: dict[str, Any]


def get_webpage_text(url: str) -> str:
    """Fetch the text content of a webpage."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # This is a simple heuristic that works for dwarkesh.com.
        # It might need to be generalized for other sites.
        transcript_div = soup.find("div", class_="transcript")
        if transcript_div:
            return transcript_div.get_text("\n")

        # Fallback for other content
        article_body = soup.find("body")
        if article_body:
            return article_body.get_text("\n")

        return ""

    except requests.RequestException as e:
        print(f"Error fetching webpage {url}: {e}")
        return ""


def parse_feed(feed_url: str, months: int = 6) -> Iterable[PodcastTranscriptEntry]:
    """Parse the podcast feed and extract transcript text from linked pages."""
    parsed = feedparser.parse(feed_url)
    if parsed.bozo:
        raise RuntimeError(f"Feed parse error: {parsed.bozo_exception}")

    cutoff = datetime.now(timezone.utc) - timedelta(days=30 * months)

    for entry in parsed.entries:
        published = None
        published_struct = entry.get("published_parsed")
        if published_struct:
            published = datetime.fromtimestamp(
                calendar.timegm(published_struct), tz=timezone.utc
            )
            if published < cutoff:
                continue

        webpage_url = entry.get("link")
        content_text = None
        if webpage_url:
            content_text = get_webpage_text(webpage_url)

        provenance = {
            key: entry.get(key)
            for key in entry.keys()
            if key.startswith("atomic_") or key.startswith("itunes_")
        }
        yield PodcastTranscriptEntry(
            id=str(entry.get("id")),
            link=str(entry.get("link")),
            title=str(entry.get("title")),
            author=entry.get("author"),
            published_at=published,
            summary=entry.get("summary"),
            content_text=content_text,
            provenance=provenance,
        )


def upsert_documents(
    conn: psycopg.Connection, source_id: str, entries: Iterable[PodcastTranscriptEntry]
) -> None:
    """Upsert podcast transcript documents into the database."""
    with conn.cursor() as cur:
        for entry in entries:
            if not entry.content_text:
                continue
            cur.execute(
                """
                INSERT INTO documents (
                    source_id, external_id, ingest_method, original_media_type,
                    original_url, title, author, published_at, ingested_at,
                    content_text, ingest_status, provenance, transcript_status
                )
                VALUES (
                    %(source_id)s, %(external_id)s, 'feed_pull', 'podcast_transcript',
                    %(original_url)s, %(title)s, %(author)s, %(published_at)s, now(),
                    %(content_text)s, 'pending_segmentation', %(provenance)s, 'completed'
                )
                ON CONFLICT (source_id, external_id)
                DO UPDATE SET
                    original_media_type = EXCLUDED.original_media_type,
                    ingest_method = EXCLUDED.ingest_method,
                    original_url = EXCLUDED.original_url,
                    title = EXCLUDED.title,
                    author = EXCLUDED.author,
                    published_at = EXCLUDED.published_at,
                    content_text = EXCLUDED.content_text,
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
                    "content_text": entry.content_text,
                    "provenance": Json(entry.provenance),
                },
            )
        conn.commit()
