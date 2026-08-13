"""
historical_store.py — Persistent SQLite storage for OSINT entries with monthly partitioning.
Retention: 90 days. Each month gets its own table (entries_YYYY_MM).
"""
import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "historical_store.db"
db_lock = threading.RLock()

RETENTION_DAYS = 90

_ENTITY_IDS_TABLE = """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
"""


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
            conn.execute(_ENTITY_IDS_TABLE)
            conn.execute(
                """CREATE TABLE IF NOT EXISTS cycle_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    cycle_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    entry_count INTEGER DEFAULT 0
                )"""
            )


def _partition_name(dt: datetime) -> str:
    return f"entries_{dt.year}_{dt.month:02d}"


def _ensure_partition(conn: sqlite3.Connection, dt: datetime):
    name = _partition_name(dt)
    conn.execute(
        f"""CREATE TABLE IF NOT EXISTS {name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id TEXT UNIQUE,
            title TEXT,
            source TEXT,
            summary TEXT,
            link TEXT,
            published TEXT,
            category TEXT,
            severity TEXT,
            sentiment TEXT,
            entities TEXT,
            cycle_id INTEGER DEFAULT 0,
            raw_data TEXT,
            ingested_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{name}_published ON {name}(published)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{name}_source ON {name}(source)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{name}_entry_id ON {name}(entry_id)"
    )


def _entry_id(entry: dict) -> str:
    link = entry.get("link") or entry.get("url") or ""
    title = entry.get("title") or ""
    pub = entry.get("published") or entry.get("published_iso") or ""
    import hashlib
    raw = f"{link}:{title}:{pub}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:24]


def store_entries(entries: List[Dict], cycle_id: int = 0, cycle_type: str = "full"):
    """Persists a batch of OSINT entries into the monthly partition."""
    if not entries:
        return 0

    _init()
    now = datetime.now()
    partition = _partition_name(now)
    ingested = now.isoformat()

    stored = 0
    with db_lock:
        with _get_conn() as conn:
            _ensure_partition(conn, now)

            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                eid = _entry_id(entry)
                try:
                    conn.execute(
                        f"""INSERT OR IGNORE INTO {partition}
                        (entry_id, title, source, summary, link, published,
                         category, severity, sentiment, entities, cycle_id,
                         raw_data, ingested_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            eid,
                            entry.get("title", "")[:500],
                            entry.get("source", "")[:100],
                            entry.get("summary", "")[:2000],
                            entry.get("link", "")[:500],
                            entry.get("published") or entry.get("published_iso") or "",
                            entry.get("category") or "",
                            entry.get("severity") or "",
                            json.dumps(entry.get("sentiment", {}), ensure_ascii=False),
                            json.dumps(entry.get("entities", []), ensure_ascii=False),
                            cycle_id,
                            json.dumps(entry, ensure_ascii=False, default=str),
                            ingested,
                        ),
                    )
                    if conn.total_changes > 0:
                        stored += 1
                except Exception as e:
                    logger.debug(f"[HISTORICAL] Skip entry {eid}: {e}")

            conn.execute(
                "INSERT INTO cycle_log (cycle_id, cycle_type, timestamp, entry_count) VALUES (?, ?, ?, ?)",
                (cycle_id, cycle_type, ingested, stored),
            )

    if stored:
        logger.info(f"[HISTORICAL] Stored {stored}/{len(entries)} entries (cycle {cycle_id})")
    _cleanup()
    return stored


def query_range(
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
    source: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> Dict[str, Any]:
    """Query historical entries by time range and optional filters."""
    _init()
    if from_dt is None:
        from_dt = datetime.now() - timedelta(days=RETENTION_DAYS)
    if to_dt is None:
        to_dt = datetime.now()

    conditions = ["published >= ?", "published <= ?"]
    params: List[Any] = [from_dt.isoformat(), to_dt.isoformat()]

    if source:
        conditions.append("source = ?")
        params.append(source)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if search:
        conditions.append("(title LIKE ? OR summary LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions)
    partitions = _get_partitions_in_range(from_dt, to_dt)

    results = []
    total = 0
    with db_lock:
        with _get_conn() as conn:
            for part in partitions:
                try:
                    row = conn.execute(
                        f"SELECT COUNT(*) as cnt FROM {part} WHERE {where}", params
                    ).fetchone()
                    total += row["cnt"] if row else 0

                    rows = conn.execute(
                        f"""SELECT id, entry_id, title, source, summary, link,
                        published, category, severity, sentiment, entities,
                        cycle_id, ingested_at
                        FROM {part} WHERE {where}
                        ORDER BY published DESC LIMIT ? OFFSET ?""",
                        params + [limit, offset],
                    ).fetchall()

                    for r in rows:
                        results.append({
                            "id": r["id"],
                            "entry_id": r["entry_id"],
                            "title": r["title"],
                            "source": r["source"],
                            "summary": r["summary"],
                            "link": r["link"],
                            "published": r["published"],
                            "category": r["category"],
                            "severity": r["severity"],
                            "sentiment": _safe_json(r["sentiment"]),
                            "entities": _safe_json(r["entities"]),
                            "cycle_id": r["cycle_id"],
                            "ingested_at": r["ingested_at"],
                        })
                except Exception as e:
                    logger.debug(f"[HISTORICAL] Skip partition {part}: {e}")

    return {"entries": results, "total": total, "from": from_dt.isoformat(), "to": to_dt.isoformat()}


def query_single(entry_id: str) -> Optional[Dict]:
    """Retrieve a single entry by its entry_id hash across all partitions."""
    _init()
    partitions = _get_all_partitions()
    with db_lock:
        with _get_conn() as conn:
            for part in partitions:
                row = conn.execute(
                    f"SELECT * FROM {part} WHERE entry_id = ?", (entry_id,)
                ).fetchone()
                if row:
                    return dict(row)
    return None


def get_stats() -> Dict:
    """Return storage statistics across all partitions."""
    _init()
    partitions = _get_all_partitions()
    total_entries = 0
    partition_stats = []
    with db_lock:
        with _get_conn() as conn:
            for part in partitions:
                try:
                    row = conn.execute(
                        f"SELECT COUNT(*) as cnt, MIN(published) as oldest, MAX(published) as newest FROM {part}"
                    ).fetchone()
                    if row and row["cnt"]:
                        total_entries += row["cnt"]
                        partition_stats.append({
                            "partition": part,
                            "entries": row["cnt"],
                            "oldest": row["oldest"],
                            "newest": row["newest"],
                        })
                except Exception:
                    pass
    return {
        "total_entries": total_entries,
        "partitions": partition_stats,
        "retention_days": RETENTION_DAYS,
        "db_path": str(DB_PATH),
    }


def delete_older_than(days: int = RETENTION_DAYS) -> int:
    """Delete entries older than N days. Returns count of deleted rows."""
    _init()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    partitions = _get_all_partitions()
    deleted = 0
    with db_lock:
        with _get_conn() as conn:
            for part in partitions:
                try:
                    cur = conn.execute(f"DELETE FROM {part} WHERE published < ?", (cutoff,))
                    deleted += cur.rowcount
                except Exception:
                    pass
    if deleted:
        logger.info(f"[HISTORICAL] Cleaned {deleted} entries older than {days}d")
    return deleted


def _cleanup():
    """Auto-cleanup: drop empty partitions and delete old entries."""
    try:
        delete_older_than(RETENTION_DAYS)
        _drop_empty_partitions()
    except Exception as e:
        logger.warning(f"[HISTORICAL] Cleanup error: {e}")


def _drop_empty_partitions():
    partitions = _get_all_partitions()
    with db_lock:
        with _get_conn() as conn:
            for part in partitions:
                try:
                    row = conn.execute(f"SELECT COUNT(*) as cnt FROM {part}").fetchone()
                    if row and row["cnt"] == 0:
                        conn.execute(f"DROP TABLE IF EXISTS {part}")
                        logger.info(f"[HISTORICAL] Dropped empty partition {part}")
                except Exception:
                    pass


def _get_all_partitions() -> List[str]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'entries_%' ORDER BY name"
        ).fetchall()
        return [r["name"] for r in rows]


def _get_partitions_in_range(from_dt: datetime, to_dt: datetime) -> List[str]:
    all_parts = _get_all_partitions()
    from_ym = f"{from_dt.year}_{from_dt.month:02d}"
    to_ym = f"{to_dt.year}_{to_dt.month:02d}"
    return [p for p in all_parts if from_ym <= p.replace("entries_", "") <= to_ym]


def _safe_json(val: str) -> Any:
    if not val:
        return {} if "sentiment" in str(val) else []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {}


def kwic_search(term: str, window_words: int = 5, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Key-Word-In-Context (KWIC) search across historical entries.
    Extracts text snippets surrounding the term.
    """
    import re
    _init()
    if not term or not term.strip():
        return []

    term_clean = term.strip()
    term_pattern = re.compile(rf'({re.escape(term_clean)})', re.IGNORECASE)
    partitions = _get_all_partitions()
    results = []

    with db_lock:
        with _get_conn() as conn:
            for part in reversed(partitions):
                sql = f"SELECT title, summary, source, published FROM {part} WHERE title LIKE ? OR summary LIKE ? ORDER BY published DESC LIMIT ?"
                rows = conn.execute(sql, (f"%{term_clean}%", f"%{term_clean}%", limit)).fetchall()
                for row in rows:
                    text = f"{row['title'] or ''}. {row['summary'] or ''}"
                    matches = list(term_pattern.finditer(text))
                    for m in matches:
                        start_idx = m.start()
                        end_idx = m.end()

                        left_text = text[:start_idx].strip()
                        right_text = text[end_idx:].strip()

                        left_words = left_text.split()[-window_words:]
                        right_words = right_text.split()[:window_words]

                        results.append({
                            "left": " ".join(left_words),
                            "keyword": m.group(0),
                            "right": " ".join(right_words),
                            "title": row["title"],
                            "source": row["source"],
                            "published": row["published"]
                        })
                        if len(results) >= limit:
                            return results
    return results

