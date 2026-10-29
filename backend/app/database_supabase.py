"""
Supabase database adapter.
Replaces the SQLite database.py with Supabase (PostgreSQL via REST API).
Uses the supabase-py SDK with the service_role (secret) key for full access.
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

_client: Client | None = None

def get_supabase() -> Client:
    """Returns a singleton Supabase client using the secret (service_role) key."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
            raise RuntimeError(
                "SUPABASE_URL e SUPABASE_SECRET_KEY não definidos no arquivo .env"
            )
        _client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    return _client


def get_setting(key: str, default: str = "") -> str:
    """Reads a key/value from the system_settings table."""
    try:
        sb = get_supabase()
        res = sb.table("system_settings").select("value").eq("key", key).limit(1).execute()
        if res and res.data:
            return res.data[0]["value"]
    except Exception:
        pass
    return default


def set_setting(key: str, value: str):
    """Upserts a key/value into the system_settings table."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    sb = get_supabase()
    sb.table("system_settings").upsert(
        {"key": key, "value": value, "updated_at": now},
        on_conflict="key"
    ).execute()
