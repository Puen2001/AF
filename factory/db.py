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
    product_id INTEGER REFERENCES products(id),   -- NULL for story-first topics
    topic_id INTEGER REFERENCES topics(id),
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
CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT
);
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,            -- trend source that surfaced it
    source_key TEXT NOT NULL UNIQUE, -- dedupe key
    title TEXT NOT NULL,             -- the story/topic in one line
    angle TEXT,                      -- curiosity angle / hook direction
    trend TEXT,                      -- the TH trend it rides
    audience_fit REAL,               -- 1-10 fit to the channel audience
    product_hint TEXT,               -- category of product that MIGHT fit, or ''
    research TEXT,                   -- cached web research brief (JSON)
    status TEXT NOT NULL DEFAULT 'discovered',  -- discovered|scripted|skipped
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or ROOT / "factory.db")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(products)")}
    for col, typ in (("score", "REAL"), ("research", "TEXT")):
        if col not in cols:
            conn.execute(f"ALTER TABLE products ADD COLUMN {col} {typ}")
    vcols = {r[1] for r in conn.execute("PRAGMA table_info(videos)")}
    if "tg_msg_id" not in vcols:
        conn.execute("ALTER TABLE videos ADD COLUMN tg_msg_id INTEGER")
    # migrate legacy scripts table: product_id was NOT NULL, and no topic_id
    sinfo = {r[1]: r for r in conn.execute("PRAGMA table_info(scripts)")}
    if "topic_id" not in sinfo:
        conn.execute("ALTER TABLE scripts ADD COLUMN topic_id INTEGER")
    if sinfo and sinfo["product_id"][3] == 1:  # notnull flag set → rebuild
        conn.executescript("""
            CREATE TABLE scripts_new (
                id INTEGER PRIMARY KEY,
                product_id INTEGER REFERENCES products(id),
                topic_id INTEGER REFERENCES topics(id),
                hook_id TEXT, body TEXT NOT NULL, factcheck TEXT,
                status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL);
            INSERT INTO scripts_new (id, product_id, hook_id, body, factcheck, status, created_at)
                SELECT id, product_id, hook_id, body, factcheck, status, created_at FROM scripts;
            DROP TABLE scripts; ALTER TABLE scripts_new RENAME TO scripts;""")
        conn.commit()
    return conn


def kv_get(conn, k: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return row["v"] if row else default


def kv_set(conn, k: str, v: str):
    conn.execute("INSERT INTO kv (k, v) VALUES (?,?) "
                 "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
    conn.commit()


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


_TABLES = {"products", "scripts", "videos", "posts", "topics"}


def rows(conn, table: str, status: str, limit: int | None = None,
         order: str = "id"):
    assert table in _TABLES, table
    q = f"SELECT * FROM {table} WHERE status=? ORDER BY {order}"
    if limit:
        q += f" LIMIT {int(limit)}"
    return conn.execute(q, (status,)).fetchall()


def set_status(conn, table: str, row_id: int, status: str):
    assert table in _TABLES, table
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
