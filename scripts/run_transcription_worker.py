import os
import time
import psycopg
from dotenv import load_dotenv
from scripts.run_transcription import run_request

load_dotenv()

def get_queued_request(db_url: str) -> str | None:
    """Fetch the oldest queued transcription request."""
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM transcription_requests WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
            )
            result = cur.fetchone()
            return result[0] if result else None

def main():
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise SystemExit("SUPABASE_DB_URL must be set")

    print("Starting transcription worker...")
    while True:
        try:
            request_id = get_queued_request(db_url)
            if request_id:
                print(f"Processing request {request_id}...")
                run_request(request_id)
            else:
                print("No queued requests found. Waiting...")
                time.sleep(10)  # Wait for 10 seconds before checking again
        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
