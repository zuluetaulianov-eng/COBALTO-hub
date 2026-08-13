"""
humint_bot.py — HUMINT field reports via Telegram bot.
Receives photos with captions, extracts geolocation from EXIF/caption,
and emits humint_report events for the dashboard.
"""
import json
import logging
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "humint_reports.db"
db_lock = threading.RLock()

# Coordinates regex: lat, lon or lat/lon
LAT_LON_RE = re.compile(
    r"(-?\d+\.?\d*)\s*[,;/\s]\s*(-?\d+\.?\d*)"
)


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
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL DEFAULT 'telegram',
                    reporter TEXT DEFAULT '',
                    report_type TEXT DEFAULT 'field_report',
                    latitude REAL,
                    longitude REAL,
                    location_name TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    photo_url TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    severity TEXT DEFAULT 'info',
                    status TEXT DEFAULT 'new',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    raw_data TEXT DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at);
                CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
            """)


def store_report(
    source: str = "telegram",
    reporter: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    location_name: str = "",
    title: str = "",
    description: str = "",
    photo_url: str = "",
    tags: Optional[List[str]] = None,
    severity: str = "info",
    raw_data: Optional[Dict] = None,
) -> str:
    """Store a HUMINT report. Returns report ID."""
    _init()
    import uuid
    rid = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat()

    with db_lock:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO reports
                (id, source, reporter, report_type, latitude, longitude,
                 location_name, title, description, photo_url, tags,
                 severity, status, created_at, updated_at, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rid, source, reporter, "field_report",
                    latitude, longitude, location_name, title[:200],
                    description[:2000] if description else "",
                    photo_url or "",
                    json.dumps(tags or []),
                    severity, "new", now, now,
                    json.dumps(raw_data or {}, ensure_ascii=False),
                ),
            )
    logger.info(f"[HUMINT] Report stored: {rid} ({title})")
    return rid


def get_reports(limit: int = 50, status: str = "", severity: str = "") -> List[Dict]:
    """Query stored HUMINT reports."""
    _init()
    conditions = []
    params = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    where = " AND ".join(conditions) if conditions else "1=1"

    with db_lock:
        with _get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM reports WHERE {where} ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()
            return [dict(r) for r in rows]


def get_report(report_id: str) -> Optional[Dict]:
    """Get a single report by ID."""
    _init()
    with db_lock:
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
            return dict(row) if row else None


def update_status(report_id: str, status: str) -> bool:
    """Mark a report as reviewed/dismissed."""
    _init()
    now = datetime.now().isoformat()
    with db_lock:
        with _get_conn() as conn:
            cur = conn.execute(
                "UPDATE reports SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, report_id),
            )
            return cur.rowcount > 0


def get_stats() -> Dict:
    """Get HUMINT report statistics."""
    _init()
    with db_lock:
        with _get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) as cnt FROM reports").fetchone()["cnt"]
            by_severity = conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM reports GROUP BY severity"
            ).fetchall()
            by_status = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM reports GROUP BY status"
            ).fetchall()
    return {
        "total": total,
        "by_severity": {r["severity"]: r["cnt"] for r in by_severity},
        "by_status": {r["status"]: r["cnt"] for r in by_status},
    }


async def run_humint_cycle():
    """Check for new reports and emit events to the dashboard."""
    from event_bus import bus
    reports = get_reports(limit=10, status="new")
    for r in reports:
        bus.emit("humint_report", source="humint_bot", data=r)
        update_status(r["id"], "published")
    return len(reports)


# ── Telegram Integration ──────────────────────────────────────────
# This function is meant to be called from telegrambot.py or as a standalone handler.

def parse_telegram_message(text: str) -> Dict:
    """Parse a Telegram message text for HUMINT data (coordinates, title, severity)."""
    result = {"latitude": None, "longitude": None, "title": "", "severity": "info"}

    # Extract coordinates
    match = LAT_LON_RE.search(text)
    if match:
        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                result["latitude"] = lat
                result["longitude"] = lon
        except ValueError:
            pass

    # Extract severity from text markers
    text_lower = text.lower()
    if any(w in text_lower for w in ["crítico", "critico", "critical", "urgente", "emergencia"]):
        result["severity"] = "critical"
    elif any(w in text_lower for w in ["alto", "alta", "high", "warning"]):
        result["severity"] = "high"
    elif any(w in text_lower for w in ["medio", "media", "medium"]):
        result["severity"] = "medium"

    # First line as title
    lines = text.strip().split("\n")
    result["title"] = lines[0][:200] if lines else "HUMINT Report"

    return result


# Standalone Telegram handler (for python-telegram-bot integration)
async def handle_telegram_photo(update, context):
    """Handle a photo message with caption from Telegram."""
    if not update.message or not update.message.photo:
        return "No photo found"

    photo = update.message.photo[-1]  # highest resolution
    caption = update.message.caption or ""
    reporter = update.effective_user.full_name if update.effective_user else "unknown"

    parsed = parse_telegram_message(caption)

    # Get location if sent as separate location message, or from caption
    lat = None
    lon = None
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
    else:
        lat = parsed["latitude"]
        lon = parsed["longitude"]

    # In production: download photo and host it
    photo_url = f"telegram:photo_id:{photo.file_id}"

    rid = store_report(
        source="telegram",
        reporter=reporter,
        latitude=lat,
        longitude=lon,
        location_name=parsed.get("location_name", ""),
        title=parsed["title"],
        description=caption,
        photo_url=photo_url,
        severity=parsed["severity"],
        tags=["telegram", "photo"],
        raw_data={"message_id": update.message.message_id, "chat_id": update.effective_chat.id if update.effective_chat else ""},
    )

    # Emit event
    try:
        from event_bus import bus
        bus.emit("humint_report", source="telegram_bot", data={
            "id": rid,
            "title": parsed["title"],
            "latitude": lat,
            "longitude": lon,
            "severity": parsed["severity"],
            "reporter": reporter,
        })
    except Exception:
        pass

    response = f"✅ Reporte HUMINT recibido: {parsed['title']}\nID: {rid}"
    if lat and lon:
        response += f"\n📍 {lat:.4f}, {lon:.4f}"
    return response
