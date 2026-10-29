import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from app.config import DB_PATH

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initializes tables if they do not exist."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table (Admin & Regular Users)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user', -- 'admin' or 'user'
            telegram_chat_id TEXT,
            failed_login_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            notification_hour INTEGER DEFAULT 22,
            email_notifications_enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """)

        # Migrate user columns if table already existed
        try:
            u_cols = [c[1] for c in cursor.execute("PRAGMA table_info(users)").fetchall()]
            if "failed_login_attempts" not in u_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
            if "locked_until" not in u_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN locked_until TEXT")
            if "notification_hour" not in u_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN notification_hour INTEGER DEFAULT 22")
            if "email_notifications_enabled" not in u_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN email_notifications_enabled INTEGER DEFAULT 1")
        except Exception:
            pass

        # Products table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT DEFAULT 'Geral',
            description TEXT,
            search_query TEXT NOT NULL,
            target_price REAL,
            image_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # Check and migrate user_id column if table already existed without it
        try:
            cols = [c[1] for c in cursor.execute("PRAGMA table_info(products)").fetchall()]
            if "user_id" not in cols:
                cursor.execute("ALTER TABLE products ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        except Exception:
            pass

        # Price Records table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            checked_at TEXT NOT NULL,
            min_price REAL NOT NULL,
            max_price REAL NOT NULL,
            avg_price REAL NOT NULL,
            best_store TEXT NOT NULL,
            best_url TEXT,
            highest_store TEXT,
            recommendation TEXT NOT NULL,
            recommendation_reason TEXT,
            delta_pct REAL DEFAULT 0.0,
            delta_amount REAL DEFAULT 0.0
        )
        """)

        # Store Offers table (individual offers found in a scrape run)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS store_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            price_record_id INTEGER NOT NULL REFERENCES price_records(id) ON DELETE CASCADE,
            store_name TEXT NOT NULL,
            product_title TEXT NOT NULL,
            price REAL NOT NULL,
            url TEXT,
            is_best INTEGER DEFAULT 0
        )
        """)

        # System Settings (Key/Value store for Telegram, n8n config, etc.)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # Telegram Notification Logs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
            channel TEXT NOT NULL DEFAULT 'telegram',
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            sent_at TEXT NOT NULL
        )
        """)

        conn.commit()

def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

def set_setting(key: str, value: str):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO system_settings (key, value, updated_at) 
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value, now))
