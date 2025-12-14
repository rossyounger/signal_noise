#!/usr/bin/env python3
"""
Script to create the Big World Hypothesis entry in the database.
Run after the 005 migration has been applied.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg
from dotenv import load_dotenv

# Load environment variables
dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

# Hypothesis data
HYPOTHESIS_TEXT = "For many learning problems, the world is multiple orders of magnitude larger than the agent, requiring approximate solutions."

DESCRIPTION = """The big world hypothesis (Javed & Sutton) argues that for many decision-making problems, agents are orders of magnitude smaller than their environments. Agents cannot fully perceive world state or represent optimal actions for every state—they must rely on approximate solutions.

**Key arguments:**

1. **Scale persists with compute growth**: As computational resources increase, both sensing capabilities (higher resolution cameras, faster sampling) and world complexity (more sophisticated agents, richer environments) grow proportionally. The agent-environment size gap remains.

2. **Implications for learning**: Big worlds require different algorithms than over-parameterized settings. Online continual learning becomes essential—agents must learn what's relevant now and discard it when no longer useful (tracking). Computationally efficient algorithms can outperform exact but expensive ones.

3. **Design consequences**: Accepting this hypothesis shifts focus from finding perfect solutions to developing algorithms that efficiently utilize limited agent resources, embrace approximation, and adapt continuously.

**Empirical support** includes AlphaZero (planning still helps after training → network lacks capacity for perfect value function) and GPT-3 scaling laws (performance improves with more parameters → under-parameterized)."""

REFERENCE_URL = "http://openreview.net/pdf?id=Sv7DazuCn8"
REFERENCE_TYPE = "paper"


def main():
    # Get database connection string
    conn_string = os.environ.get("SUPABASE_CONN_STRING") or os.environ.get("SUPABASE_DB_URL")
    
    if not conn_string:
        print("ERROR: SUPABASE_CONN_STRING or SUPABASE_DB_URL not found in environment variables.")
        sys.exit(1)
    
    print("Connecting to database...")
    
    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                # Check if hypothesis already exists
                cur.execute(
                    "SELECT id FROM hypotheses WHERE hypothesis_text = %s",
                    (HYPOTHESIS_TEXT,)
                )
                existing = cur.fetchone()
                
                if existing:
                    print(f"✓ Big World Hypothesis already exists with ID: {existing[0]}")
                    return
                
                # Insert the hypothesis
                cur.execute(
                    """
                    INSERT INTO hypotheses (hypothesis_text, description, reference_url, reference_type)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (HYPOTHESIS_TEXT, DESCRIPTION, REFERENCE_URL, REFERENCE_TYPE)
                )
                
                hypothesis_id = cur.fetchone()[0]
                conn.commit()
                
                print(f"✓ Successfully created Big World Hypothesis with ID: {hypothesis_id}")
                print(f"  - Hypothesis: {HYPOTHESIS_TEXT[:80]}...")
                print(f"  - Reference: {REFERENCE_URL}")
                print(f"  - Type: {REFERENCE_TYPE}")
                
    except Exception as e:
        print(f"ERROR: Failed to create hypothesis: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
