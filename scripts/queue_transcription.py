"""Queue a transcription request for a document."""

from __future__ import annotations

import argparse
import os

import psycopg


def parse_timecode(value: str | None) -> float | None:
    if not value:
        return None
    parts = value.split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Invalid timecode format")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def insert_request(
    db_url: str,
    document_id: str,
    provider: str,
    model: str | None,
    start_seconds: float | None,
    end_seconds: float | None,
) -> str:
    insert_sql = """
        INSERT INTO transcription_requests (
            document_id,
            provider,
            model,
            start_seconds,
            end_seconds
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    with psycopg.connect(db_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            insert_sql,
            (document_id, provider, model, start_seconds, end_seconds),
        )
        request_id = cur.fetchone()[0]
    return request_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue a transcription request")
    parser.add_argument("document_id", help="Document UUID to transcribe")
    parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "assemblyai"],
        help="Transcription provider",
    )
    parser.add_argument("--model", help="Model identifier for the provider")
    parser.add_argument("--start", help="Start time (HH:MM:SS)")
    parser.add_argument("--end", help="End time (HH:MM:SS)")
    args = parser.parse_args()

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise SystemExit("SUPABASE_DB_URL must be set")

    start_seconds = parse_timecode(args.start)
    end_seconds = parse_timecode(args.end)

    request_id = insert_request(
        db_url=db_url,
        document_id=args.document_id,
        provider=args.provider,
        model=args.model,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
    )

    print(f"Queued transcription request {request_id}")


if __name__ == "__main__":
    main()
