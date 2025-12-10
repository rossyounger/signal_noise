#!/usr/bin/env python3
"""Run a SQL migration file against the database."""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Load .env from project root
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path, override=True)


def run_migration(migration_file: str):
    """Run a SQL migration file."""
    db_url = os.environ.get("SUPABASE_CONN_STRING") or os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("Error: SUPABASE_CONN_STRING or SUPABASE_DB_URL not found in environment variables.")
        sys.exit(1)

    migration_path = Path(__file__).resolve().parent.parent / "sql" / migration_file
    if not migration_path.exists():
        print(f"Error: Migration file not found: {migration_path}")
        sys.exit(1)

    print(f"Running migration: {migration_file}")
    print(f"File: {migration_path}")
    
    sql_content = migration_path.read_text()
    
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql_content)
        print("✓ Migration completed successfully!")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_migration.py <migration_file>")
        print("Example: python scripts/run_migration.py 003_remove_topic_ids_name.sql")
        sys.exit(1)
    
    run_migration(sys.argv[1])

