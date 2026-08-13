"""
agent_memory.py — Persistent session memory for autonomous agents.
Stores reasoning history, context windows, and tool call results in SQLite.
"""
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "agent_memory.db"
db_lock = threading.RLock()

_RETENTION_HOURS = 72
_MAX_CONTEXT_WINDOW = 50


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def _init():
    with db_lock:
        with _get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    context_summary TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS context_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_name TEXT DEFAULT '',
                    tool_result TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_context_session ON context_entries(session_id);
                CREATE INDEX IF NOT EXISTS idx_context_created ON context_entries(created_at);
            """)


def create_session(agent_name: str, session_id: str = "") -> str:
    """Create a new agent session. Returns session_id."""
    _init()
    import uuid
    sid = session_id or uuid.uuid4().hex[:16]
    now = datetime.now().isoformat()
    with db_lock:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions (session_id, agent_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (sid, agent_name, now, now),
            )
    logger.debug(f"[AGENT MEMORY] Session created: {sid} for {agent_name}")
    return sid


def append_context(session_id: str, role: str, content: str, tool_name: str = "", tool_result: str = ""):
    """Add a context entry to a session."""
    _init()
    now = datetime.now().isoformat()
    with db_lock:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO context_entries
                (session_id, role, content, tool_name, tool_result, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, role, content[:2000], tool_name, str(tool_result)[:2000], now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now, session_id)
            )
    _trim_context(session_id)


def get_context(session_id: str, limit: int = _MAX_CONTEXT_WINDOW) -> List[Dict]:
    """Get recent context entries for a session."""
    _init()
    with db_lock:
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT role, content, tool_name, tool_result, created_at
                FROM context_entries WHERE session_id = ?
                ORDER BY id DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
            return [
                {
                    "role": r["role"],
                    "content": r["content"],
                    "tool_name": r["tool_name"],
                    "tool_result": r["tool_result"],
                    "created_at": r["created_at"],
                }
                for r in reversed(rows)
            ]


def get_session(session_id: str) -> Optional[Dict]:
    """Get session metadata."""
    _init()
    with db_lock:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "agent_name": row["agent_name"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "context_count": conn.execute(
                        "SELECT COUNT(*) as cnt FROM context_entries WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()["cnt"],
                }
    return None


def list_sessions(agent_name: Optional[str] = None, limit: int = 20) -> List[Dict]:
    """List recent sessions."""
    _init()
    with db_lock:
        with _get_conn() as conn:
            if agent_name:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE agent_name = ? ORDER BY updated_at DESC LIMIT ?",
                    (agent_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]


def _trim_context(session_id: str):
    """Keep only the last MAX_CONTEXT_WINDOW entries per session."""
    with db_lock:
        with _get_conn() as conn:
            conn.execute(
                """DELETE FROM context_entries WHERE session_id = ? AND id NOT IN (
                    SELECT id FROM context_entries WHERE session_id = ?
                    ORDER BY id DESC LIMIT ?
                )""",
                (session_id, session_id, _MAX_CONTEXT_WINDOW),
            )


def cleanup():
    """Remove sessions older than RETENTION_HOURS."""
    _init()
    cutoff = (datetime.now() - timedelta(hours=_RETENTION_HOURS)).isoformat()
    with db_lock:
        with _get_conn() as conn:
            conn.execute("DELETE FROM context_entries WHERE created_at < ?", (cutoff,))
            conn.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
