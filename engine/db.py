"""SQLite storage. One file, no server, so the engine runs anywhere Python runs."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "setu.db"

# Columns stored as JSON text and decoded on read.
JSON_COLS = {"payload", "meddpicc", "reasoning", "evidence", "counter_signals",
             "action", "adjustment", "detail", "stats", "value", "aliases"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, domain TEXT UNIQUE, country TEXT,
    region TEXT, territory TEXT, industry TEXT, employees INTEGER,
    is_customer INTEGER DEFAULT 0, arr_eur REAL DEFAULT 0, usage_trend REAL DEFAULT 0,
    corridor TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS stakeholders (
    id TEXT PRIMARY KEY, account_id TEXT REFERENCES accounts(id), name TEXT, title TEXT,
    role TEXT, email TEXT, influence INTEGER DEFAULT 3, last_engaged TEXT,
    status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY, name TEXT, aliases TEXT, positioning TEXT
);
CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY, account_id TEXT REFERENCES accounts(id), name TEXT,
    amount REAL, currency TEXT DEFAULT 'EUR', fx_at_quote REAL, stage TEXT,
    close_date TEXT, original_close_date TEXT, forecast_category TEXT, owner TEXT,
    meddpicc TEXT, last_activity TEXT, status TEXT DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, occurred_at TEXT, text TEXT,
    payload TEXT, kind TEXT, sentiment REAL DEFAULT 0, account_id TEXT,
    opportunity_id TEXT, stakeholder_id TEXT, competitor_id TEXT,
    resolved INTEGER DEFAULT 0, ingested_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, finished_at TEXT,
    stats TEXT, briefing TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, agent TEXT, type TEXT,
    key TEXT, title TEXT, account_id TEXT, opportunity_id TEXT, owner TEXT,
    recommendation TEXT, reasoning TEXT, evidence TEXT, counter_signals TEXT,
    confidence REAL, impact_eur REAL, urgency REAL, strategic_fit REAL, priority REAL,
    status TEXT DEFAULT 'pending', action TEXT, created_at TEXT, updated_at TEXT,
    reviewed_by TEXT, review_note TEXT, adjustment TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, action TEXT,
    decision_id INTEGER, detail TEXT
);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, channel TEXT, target TEXT,
    payload TEXT, status TEXT DEFAULT 'queued', decision_id INTEGER
);
CREATE TABLE IF NOT EXISTS agent_weights (
    agent TEXT PRIMARY KEY, weight REAL DEFAULT 1.0, approved INTEGER DEFAULT 0,
    adjusted INTEGER DEFAULT 0, rejected INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


def connect(path=None):
    target = str(path or os.environ.get("SETU_DB", DEFAULT_DB))
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def j(value):
    return json.dumps(value, ensure_ascii=False)


def _decode(row):
    d = dict(row)
    for k in JSON_COLS & d.keys():
        if isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                pass
    return d


def rows(conn, sql, args=()):
    return [_decode(r) for r in conn.execute(sql, args).fetchall()]


def one(conn, sql, args=()):
    r = conn.execute(sql, args).fetchone()
    return _decode(r) if r else None


def get_setting(conn, key, default=None):
    r = one(conn, "SELECT value FROM settings WHERE key = ?", (key,))
    return r["value"] if r else default


def set_setting(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, j(value)))


def audit(conn, actor, action, decision_id=None, detail=None):
    conn.execute("INSERT INTO audit_log (ts, actor, action, decision_id, detail) VALUES (?, ?, ?, ?, ?)",
                 (now_iso(), actor, action, decision_id, j(detail or {})))
