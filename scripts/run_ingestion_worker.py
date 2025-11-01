import os
import time
import psycopg
from dotenv import load_dotenv
from scripts.run_ingestion import run_source_ingestion

load_dotenv()

def process_queued_requests(db_url: str):
    """Fetch and process one queued ingestion request."""
    # Using a FOR UPDATE SKIP LOCKED to allow multiple workers in the future
    sql = """
        UPDATE ingestion_requests
        SET status = 'in_progress'
        WHERE id = (
            SELECT id
            FROM ingestion_requests
            WHERE status = 'queued'
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        RETURNING id, source_id;
    """
    job_id, source_id = None, None
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            result = cur.fetchone()
            if result:
                job_id, source_id = result

    if job_id and source_id:
        print(f"Processing ingestion job {job_id} for source {source_id}...")
        try:
            run_source_ingestion(db_url, source_id)
            status, error = "completed", None
        except Exception as e:
            print(f"Error processing job {job_id}: {e}")
            status, error = "failed", str(e)

        # Update the job status
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ingestion_requests SET status = %s, error_message = %s WHERE id = %s",
                    (status, error, job_id),
                )
    else:
        # No job found, wait
        time.sleep(10)

def main():
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise SystemExit("SUPABASE_DB_URL must be set")

    print("Starting ingestion worker...")
    while True:
        process_queued_requests(db_url)

if __name__ == "__main__":
    main()
