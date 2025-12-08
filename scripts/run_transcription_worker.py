import os
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
from scripts.run_transcription import process_transcription_request

load_dotenv()

def claim_pending_request(conn: psycopg.Connection) -> tuple[str, str] | None:
    """Fetch the next pending transcription request and mark it in progress."""
    sql = """
        UPDATE transcription_requests
        SET status = 'in_progress'
        WHERE id = (
            SELECT id
            FROM transcription_requests
            WHERE status = 'pending'
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        RETURNING id, provider;
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
    if not row:
        return None
    return row[0], row[1]


def mark_completed(conn: psycopg.Connection, request_id: str, transcript: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE transcription_requests
            SET status = 'completed',
                result_text = %s,
                metadata = COALESCE(metadata, '{}'::jsonb) - 'error'
            WHERE id = %s
            """,
            (transcript, request_id),
        )


def mark_failed(conn: psycopg.Connection, request_id: str, error_message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE transcription_requests
            SET status = 'failed',
                result_text = NULL,
                metadata = COALESCE(metadata, '{}'::jsonb) || %s
            WHERE id = %s
            """,
            (Jsonb({"error": error_message}), request_id),
        )


def main():
    db_url_raw = os.environ.get("SUPABASE_DB_URL")
    if not db_url_raw:
        raise SystemExit("SUPABASE_DB_URL must be set")

    # Add a connection timeout to handle potential network issues
    parts = urlparse(db_url_raw)
    query_params = parse_qs(parts.query)
    query_params["connect_timeout"] = ["10"]
    new_query = urlencode(query_params, doseq=True)
    new_parts = parts._replace(query=new_query)
    db_url = urlunparse(new_parts)

    print("Starting transcription worker...")
    while True:
        with psycopg.connect(db_url, autocommit=True) as conn:
            request_info = claim_pending_request(conn)

        if not request_info:
            print("No pending requests found. Waiting bro...")
            time.sleep(10)
            continue

        request_id, provider = request_info
        print(f"Processing request {request_id} with provider {provider}...")

        with psycopg.connect(db_url, autocommit=False) as conn:
            try:
                transcript = process_transcription_request(conn, request_id)
                mark_completed(conn, request_id, transcript)
                conn.commit()
                print(f"Completed request {request_id}.")
            except Exception as exc:  # noqa: BLE001 (worker should surface provider errors)
                conn.rollback()
                error_message = str(exc)
                # Avoid unbounded error payloads in metadata
                trimmed_error = error_message[:500]
                mark_failed(conn, request_id, trimmed_error)
                conn.commit()
                print(f"Failed request {request_id}: {error_message}")

if __name__ == "__main__":
    main()
