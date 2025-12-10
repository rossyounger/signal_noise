from pathlib import Path
from dotenv import load_dotenv
import os

# Mimic src/api.py logic
current_file = Path(__file__).resolve()
# src/api.py is in src/, so it does parent.parent.
# This script will be in scripts/, so it should also do parent.parent to get to root.
# Let's verify where we think root is.

# If this script is in scripts/debug_env.py:
# parent = scripts/
# parent.parent = root/
dotenv_path = current_file.parent.parent / ".env"

print(f"Looking for .env at: {dotenv_path}")
print(f"File exists? {dotenv_path.exists()}")

load_dotenv(dotenv_path=dotenv_path, override=True)

print("--- Environment Keys found (values hidden) ---")
keys = ["SUPABASE_DB_URL", "SUPABASE_CONN_STRING", "OPENAI_API_KEY", "ASSEMBLYAI_API_KEY"]
for k in keys:
    val = os.environ.get(k)
    found = "✅ Found" if val else "❌ Missing"
    print(f"{k}: {found}")
    if val:
        print(f"   Value length: {len(val)}")
