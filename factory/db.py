"""SQLite state machine for the pipeline. One file: factory.db."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,            -- seed | shopee_feed | trends
    source_key TEXT NOT NULL UNIQUE, -- dedupe key
    name TEXT NOT NULL,
    category TEXT,
    price_thb REAL,
    url TEXT,
    affiliate_link TEXT,
    facts TEXT,                      -- JSON list of allowed claims
    status TEXT NOT NULL DEFAULT 'discovered',  -- discovered|scripted|skipped
    discovered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    hook_id TEXT,
    body TEXT NOT NULL,              -- JSON: {hook, lines[], caption, hashtags[], cta}
    factcheck TEXT,                  -- JSON: {verdict, issues[]}
    status TEXT NOT NULL DEFAULT 'draft',  -- draft|checked|rejected
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY,
    script_id INTEGER NOT NULL REFERENCES scripts(id),
    template TEXT,
    file TEXT,
    status TEXT NOT NULL DEFAULT 'rendered',
    -- rendered|pending_approval|approved|rejected|posted
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id),
    platform TEXT NOT NULL,          -- youtube|tiktok
    url TEXT,
    posted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(id),
    captured_at TEXT NOT NULL,
    views INTEGER, likes INTEGER, clicks INTEGER, commissions_thb REAL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or ROOT / "factory.db")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_product(conn, *, source, source_key, name, category=None, price_thb=None,
                   url=None, affiliate_link=None, facts=None) -> bool:
    """Insert if new; returns True when inserted."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO products "
        "(source, source_key, name, category, price_thb, url, affiliate_link, facts, discovered_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (source, source_key, name, category, price_thb, url, affiliate_link, facts, now()),
    )
    conn.commit()
    return cur.rowcount > 0


def rows(conn, table: str, status: str, limit: int | None = None):
    q = f"SELECT * FROM {table} WHERE status=? ORDER BY id"
    if limit:
        q += f" LIMIT {int(limit)}"
    return conn.execute(q, (status,)).fetchall()


def set_status(conn, table: str, row_id: int, status: str):
    conn.execute(f"UPDATE {table} SET status=? WHERE id=?", (status, row_id))
    conn.commit()


def counts(conn) -> dict:
    out = {}
    for table in ("products", "scripts", "videos", "posts"):
        for r in conn.execute(f"SELECT status, COUNT(*) n FROM {table} GROUP BY status"
                              if table != "posts" else
                              f"SELECT platform status, COUNT(*) n FROM posts GROUP BY platform"):
            out[f"{table}.{r['status']}"] = r["n"]
    return out
