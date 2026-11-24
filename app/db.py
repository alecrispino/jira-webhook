"""SQLite-Zugriff mit der Standardbibliothek.

- jira_events: append-only Audit-Log, jedes Event als rohes JSON.
- issues:      aktueller Stand pro Issue (Upsert), Grundlage für /stats.
"""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Dict

from app.schemas import JiraEvent

NO_URGENCY = "none"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jira_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    issue_key   TEXT NOT NULL,
    payload     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jira_events_issue_key ON jira_events(issue_key);

-- Append-only auf DB-Ebene erzwingen, nicht nur per Konvention im Code.
CREATE TRIGGER IF NOT EXISTS jira_events_no_update
BEFORE UPDATE ON jira_events
BEGIN SELECT RAISE(ABORT, 'jira_events is append-only'); END;

CREATE TRIGGER IF NOT EXISTS jira_events_no_delete
BEFORE DELETE ON jira_events
BEGIN SELECT RAISE(ABORT, 'jira_events is append-only'); END;

CREATE TABLE IF NOT EXISTS issues (
    key        TEXT PRIMARY KEY,
    summary    TEXT NOT NULL,
    status     TEXT NOT NULL,
    urgency    TEXT,
    updated_at TEXT NOT NULL
);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    # Eine Verbindung pro Aufruf: sqlite3-Verbindungen nicht zwischen Threads teilen.
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    with closing(_connect(db_path)) as conn:
        # WAL: Leser (/stats) blockieren Schreiber (/webhook) nicht.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)


def record_event(db_path: str, raw_payload: str, event: JiraEvent) -> int:
    """Schreibt Audit-Eintrag und Upsert in EINER Transaktion: entweder beides oder nichts."""
    now = datetime.now(timezone.utc).isoformat()
    with closing(_connect(db_path)) as conn, conn:  # zweites `conn`: commit/rollback
        cur = conn.execute(
            "INSERT INTO jira_events (received_at, issue_key, payload) VALUES (?, ?, ?)",
            (now, event.key, raw_payload),
        )
        conn.execute(
            """
            INSERT INTO issues (key, summary, status, urgency, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                summary    = excluded.summary,
                status     = excluded.status,
                urgency    = excluded.urgency,
                updated_at = excluded.updated_at
            """,
            (event.key, event.summary, event.status, event.urgency, now),
        )
        return cur.lastrowid


def get_stats(db_path: str) -> Dict[str, Dict[str, int]]:
    with closing(_connect(db_path)) as conn:
        by_status = conn.execute(
            "SELECT status, COUNT(*) FROM issues GROUP BY status ORDER BY status"
        ).fetchall()
        by_urgency = conn.execute(
            "SELECT COALESCE(urgency, ?), COUNT(*) FROM issues GROUP BY 1 ORDER BY 1",
            (NO_URGENCY,),
        ).fetchall()
    return {"by_status": dict(by_status), "by_urgency": dict(by_urgency)}
