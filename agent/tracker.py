"""The tracker: one SQLite file that remembers every brand, message and reply.

Everything else in the agent reads and writes through here, so there is a single
source of truth for "who have we contacted, with what, and did they answer".
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "leads.db"

# The pipeline every prospect moves through, in order.
STATUSES = [
    "new",          # found, not yet screened
    "skipped",      # past client or duplicate, never contacted
    "matched",      # screened and paired with a portfolio piece
    "drafted",      # message written and scored by the critic
    "sent",         # the creator pressed send (only a human sets this)
    "replied",      # an answer arrived in Gmail or the IG inbox
    "won",          # turned into paid work
    "lost",         # said no, or went cold after follow-ups
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS past_clients (
    id INTEGER PRIMARY KEY,
    brand TEXT NOT NULL,
    handle TEXT,
    email TEXT,
    last_project TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY,
    brand TEXT NOT NULL,
    handle TEXT,
    email TEXT,
    niche TEXT,
    followers INTEGER,
    source TEXT,
    why TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    skip_reason TEXT,
    portfolio_item TEXT,
    match_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    channel TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'first_touch',
    portfolio_item TEXT,
    message TEXT NOT NULL,
    critic_score INTEGER,
    critic_notes TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT
);
CREATE TABLE IF NOT EXISTS replies (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    channel TEXT NOT NULL,
    external_id TEXT UNIQUE,
    received_at TEXT NOT NULL,
    body TEXT NOT NULL,
    intent TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    prospect_id INTEGER,
    detail TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def connect(db_path: Path | None = None):
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init(db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def log(conn, actor: str, action: str, prospect_id: int | None = None, detail: dict | str | None = None) -> None:
    if isinstance(detail, dict):
        detail = json.dumps(detail)
    conn.execute(
        "INSERT INTO events (at, actor, action, prospect_id, detail) VALUES (?,?,?,?,?)",
        (now(), actor, action, prospect_id, detail),
    )


def set_status(conn, prospect_id: int, status: str, actor: str, **fields) -> None:
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; expected one of {STATUSES}")
    cols = ", ".join(f"{k} = ?" for k in fields)
    sql = f"UPDATE prospects SET status = ?, updated_at = ?{', ' + cols if cols else ''} WHERE id = ?"
    conn.execute(sql, (status, now(), *fields.values(), prospect_id))
    log(conn, actor, f"status:{status}", prospect_id, fields or None)


def add_prospect(conn, *, brand: str, handle: str | None = None, email: str | None = None,
                 niche: str | None = None, followers: int | None = None,
                 source: str | None = None, why: str | None = None, actor: str = "agent") -> int:
    ts = now()
    cur = conn.execute(
        """INSERT INTO prospects (brand, handle, email, niche, followers, source, why,
                                  status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?, 'new', ?, ?)""",
        (brand, handle, email, niche, followers, source, why, ts, ts),
    )
    log(conn, actor, "add_prospect", cur.lastrowid, {"brand": brand, "source": source})
    return cur.lastrowid


def add_past_client(conn, *, brand: str, handle: str | None = None, email: str | None = None,
                    last_project: str | None = None, notes: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO past_clients (brand, handle, email, last_project, notes) VALUES (?,?,?,?,?)",
        (brand, handle, email, last_project, notes),
    )
    return cur.lastrowid


def funnel(conn) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for row in conn.execute("SELECT status, COUNT(*) n FROM prospects GROUP BY status"):
        counts[row["status"]] = row["n"]
    return counts
