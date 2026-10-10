import datetime
import os
import sqlite3

from app.config import BACKEND_DIR

DB_PATH = os.getenv("DB_PATH") or os.path.join(BACKEND_DIR, "data", "app.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    items TEXT NOT NULL,
    amount INTEGER NOT NULL,
    city TEXT NOT NULL,
    address TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    started_at TEXT,
    ended_at TEXT,
    outcome TEXT,
    needs_review INTEGER DEFAULT 0,
    review_reason TEXT,
    summary TEXT
);
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id INTEGER NOT NULL REFERENCES calls(id),
    idx INTEGER,
    speaker TEXT,
    text TEXT,
    intent TEXT,
    retrieved TEXT,
    llm_ms INTEGER,
    created_at TEXT
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row      # rows behave like dictionaries
    return conn


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)
        # Migration: add columns that older databases don't have yet
        existing = {row["name"] for row in c.execute("PRAGMA table_info(turns)")}
        for column, col_type in [("asr_ms", "INTEGER"), ("tts_ms", "INTEGER"), ("audio", "TEXT")]:
            if column not in existing:
                c.execute(f"ALTER TABLE turns ADD COLUMN {column} {col_type}")


def create_order(name, phone, items, amount, city, address):
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO orders (customer_name, phone, items, amount, city, address, status, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)",
            (name, phone, items, amount, city, address, now()),
        )
        return cur.lastrowid


def get_order(order_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None


def list_orders():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM orders ORDER BY id")]


def update_order(order_id, status, address=None):
    with _conn() as c:
        if address:
            c.execute("UPDATE orders SET status = ?, address = ?, updated_at = ? WHERE id = ?",
                      (status, address, now(), order_id))
        else:
            c.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
                      (status, now(), order_id))


def create_call(order_id):
    with _conn() as c:
        return c.execute("INSERT INTO calls (order_id, started_at) VALUES (?, ?)",
                         (order_id, now())).lastrowid


def add_turn(call_id, idx, speaker, text, intent=None, retrieved=None, llm_ms=None):
    with _conn() as c:
        c.execute(
            "INSERT INTO turns (call_id, idx, speaker, text, intent, retrieved, llm_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (call_id, idx, speaker, text, intent, retrieved, llm_ms, now()),
        )


def end_call(call_id, outcome, needs_review, review_reason, summary):
    with _conn() as c:
        c.execute(
            "UPDATE calls SET ended_at = ?, outcome = ?, needs_review = ?, review_reason = ?, summary = ? "
            "WHERE id = ?",
            (now(), outcome, int(needs_review), review_reason, summary, call_id),
        )

def set_turn_extra(call_id, idx, asr_ms=None, tts_ms=None, audio=None):
    """Add timing / audio info to a turn the agent already logged."""
    fields = {"asr_ms": asr_ms, "tts_ms": tts_ms, "audio": audio}
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE turns SET {assignments} WHERE call_id = ? AND idx = ?",
                  (*fields.values(), call_id, idx))


def list_calls(limit=50):
    with _conn() as c:
        rows = c.execute(
            "SELECT calls.*, orders.customer_name, orders.amount "
            "FROM calls JOIN orders ON orders.id = calls.order_id "
            "ORDER BY calls.id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]


def get_call(call_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        return dict(row) if row else None


def get_turns(call_id):
    with _conn() as c:
        rows = c.execute("SELECT * FROM turns WHERE call_id = ? ORDER BY idx", (call_id,))
        return [dict(r) for r in rows]