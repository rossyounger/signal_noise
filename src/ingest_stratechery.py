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
import requests
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


def _fetch_feed(feed_url: str) -> feedparser.FeedParserDict:
    """Fetch and parse an RSS/Atom feed with a browser-like user agent.

    Some providers (e.g. dwarkesh.com) return HTTP 403 when contacted by the
    default urllib user agent that feedparser uses internally. We fetch the
    feed ourselves with requests and pass the bytes to feedparser to avoid
    that issue.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SignalNoiseIngest/1.0; +https://signal-noise)",
        "Accept": "application/rss+xml, application/atom+xml;q=0.9, */*;q=0.8",
    }
    try:
        response = requests.get(feed_url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Feed fetch error: {exc}") from exc

    parsed = feedparser.parse(response.content)
    if parsed.bozo:
        raise RuntimeError(f"Feed parse error: {parsed.bozo_exception}")
    return parsed


def parse_feed(feed_url: str) -> Iterable[FeedEntry]:
    parsed = _fetch_feed(feed_url)

    for entry in parsed.entries:
        content_list = entry.get("content", [])
        content_html = ""
        if content_list:
            content_html = content_list[0].get("value", "")
        else:
            summary = entry.get("summary")
            if summary:
                content_html = summary
        if not content_html:
            continue
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
                    ingest_method = EXCLUDED.ingest_method,
                    original_media_type = EXCLUDED.original_media_type,
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
