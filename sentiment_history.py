"""
COBALTO HUB — Sentiment History Store
Persiste cada ciclo de análisis en SQLite para tendencias de largo plazo.
"""
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "sentiment_history.db"

_DB_URL = os.getenv("DATABASE_URL")
_USE_PG = bool(_DB_URL and "postgres" in _DB_URL)
if _USE_PG:
    _PG_URL = _DB_URL.replace("postgresql+asyncpg://", "postgresql://")

# ── Schema ────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS sentiment_cycles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    score_global    REAL NOT NULL,
    nivel_alerta    TEXT NOT NULL,
    color_alerta    TEXT NOT NULL,
    bot_rate        REAL NOT NULL,
    bots_detectados INTEGER NOT NULL,
    alertas_criticas INTEGER NOT NULL,
    alertas_atencion INTEGER NOT NULL,
    total_analizadas INTEGER NOT NULL,
    dist_positivo   INTEGER NOT NULL,
    dist_neutro     INTEGER NOT NULL,
    dist_negativo   INTEGER NOT NULL,
    emo_ira         INTEGER NOT NULL,
    emo_miedo       INTEGER NOT NULL,
    emo_esperanza   INTEGER NOT NULL,
    top_palabras_pos TEXT,
    top_palabras_neg TEXT,
    narrativas_geo  TEXT
);

CREATE TABLE IF NOT EXISTS content_hash_cache (
    hash TEXT PRIMARY KEY,
    ts   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cycles_ts ON sentiment_cycles(ts);
"""

_DDL_PG = """
CREATE TABLE IF NOT EXISTS sentiment_cycles (
    id              SERIAL PRIMARY KEY,
    ts              TEXT NOT NULL,
    score_global    REAL NOT NULL,
    nivel_alerta    TEXT NOT NULL,
    color_alerta    TEXT NOT NULL,
    bot_rate        REAL NOT NULL,
    bots_detectados INTEGER NOT NULL,
    alertas_criticas INTEGER NOT NULL,
    alertas_atencion INTEGER NOT NULL,
    total_analizadas INTEGER NOT NULL,
    dist_positivo   INTEGER NOT NULL,
    dist_neutro     INTEGER NOT NULL,
    dist_negativo   INTEGER NOT NULL,
    emo_ira         INTEGER NOT NULL,
    emo_miedo       INTEGER NOT NULL,
    emo_esperanza   INTEGER NOT NULL,
    top_palabras_pos TEXT,
    top_palabras_neg TEXT,
    narrativas_geo  TEXT
);

CREATE TABLE IF NOT EXISTS content_hash_cache (
    hash TEXT PRIMARY KEY,
    ts   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cycles_ts ON sentiment_cycles(ts);
"""

_DB_INITIALIZED = False

class DBWrapper:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=()):
        if _USE_PG:
            query = query.replace("?", "%s")
            if "INSERT OR IGNORE" in query:
                query = query.replace("INSERT OR IGNORE INTO content_hash_cache", "INSERT INTO content_hash_cache")
                query += " ON CONFLICT (hash) DO NOTHING"
            cur = self.conn.cursor()
            cur.execute(query, params)
            return cur
        else:
            return self.conn.execute(query, params)

    def executemany(self, query, params):
        if _USE_PG:
            query = query.replace("?", "%s")
            if "INSERT OR IGNORE" in query:
                query = query.replace("INSERT OR IGNORE INTO content_hash_cache", "INSERT INTO content_hash_cache")
                query += " ON CONFLICT (hash) DO NOTHING"
            cur = self.conn.cursor()
            cur.executemany(query, params)
            return cur
        else:
            return self.conn.executemany(query, params)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def _get_conn() -> DBWrapper:
    global _DB_INITIALIZED
    if _USE_PG:
        import psycopg2
        from psycopg2.extras import DictCursor
        conn = psycopg2.connect(_PG_URL, cursor_factory=DictCursor)
        if not _DB_INITIALIZED:
            with conn.cursor() as cur:
                cur.execute(_DDL_PG)
            conn.commit()
            _DB_INITIALIZED = True
        return DBWrapper(conn)
    else:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        if not _DB_INITIALIZED:
            conn.executescript(_DDL)
            conn.commit()
            _DB_INITIALIZED = True
        return DBWrapper(conn)


# ── Escritura ─────────────────────────────────────────────────────────────────

def save_cycle(data: dict) -> bool:
    """Persiste el resultado de get_sentiment_data() en la BD histórica."""
    try:
        conn = _get_conn()
        dist = data.get("distribucion", {})
        emo  = data.get("emociones", {})
        conn.execute("""
            INSERT INTO sentiment_cycles
            (ts, score_global, nivel_alerta, color_alerta, bot_rate,
             bots_detectados, alertas_criticas, alertas_atencion, total_analizadas,
             dist_positivo, dist_neutro, dist_negativo,
             emo_ira, emo_miedo, emo_esperanza,
             top_palabras_pos, top_palabras_neg, narrativas_geo)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            data.get("score_global", 0.0),
            data.get("nivel_alerta", "NORMAL"),
            data.get("color_alerta", "#44aaee"),
            data.get("bot_rate", 0.0),
            data.get("bots_detectados", 0),
            data.get("alertas_criticas", 0),
            data.get("alertas_atencion", 0),
            data.get("total_analizadas", 0),
            dist.get("positivo", 0),
            dist.get("neutro", 0),
            dist.get("negativo", 0),
            emo.get("ira", 0),
            emo.get("miedo", 0),
            emo.get("esperanza", 0),
            json.dumps(data.get("top_palabras_pos", []), ensure_ascii=False),
            json.dumps(data.get("top_palabras_neg", []), ensure_ascii=False),
            json.dumps(data.get("narrativas_geo", []), ensure_ascii=False),
        ))
        conn.commit()
        conn.close()
        logger.info("[SENT-HIST] Ciclo guardado en historial.")
        return True
    except Exception as e:
        logger.error(f"[SENT-HIST] Error guardando ciclo: {e}")
        return False


# ── Lectura ───────────────────────────────────────────────────────────────────

def get_history(hours: int = 168, limit: int = 500) -> list[dict]:
    """Devuelve los ciclos de las últimas N horas (default 7 días = 168h)."""
    try:
        conn = _get_conn()
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = conn.execute("""
            SELECT * FROM sentiment_cycles
            WHERE ts >= ?
            ORDER BY ts DESC
            LIMIT ?
        """, (since, limit)).fetchall()
        conn.close()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[SENT-HIST] Error leyendo historial: {e}")
        return []


def get_trend_series(hours: int = 48, bucket_hours: int = 1) -> list[dict]:
    """
    Agrega el historial en buckets de N horas para gráfico de tendencia.
    Devuelve lista de {ts, score_global, bot_rate, nivel_alerta, total}.
    """
    rows = get_history(hours=hours)
    if not rows:
        return []

    # Agrupar por bucket
    buckets: dict[str, list] = {}
    for row in rows:
        try:
            dt = datetime.fromisoformat(row["ts"])
            # Redondear al bucket
            bucket_dt = dt.replace(
                minute=0, second=0, microsecond=0,
                hour=(dt.hour // bucket_hours) * bucket_hours
            )
            key = bucket_dt.strftime("%Y-%m-%dT%H:00")
            buckets.setdefault(key, []).append(row)
        except Exception:
            continue

    result = []
    for key in sorted(buckets.keys()):
        group = buckets[key]
        scores = [r["score_global"] for r in group]
        bot_rates = [r["bot_rate"] for r in group]
        avg_score = round(sum(scores) / len(scores), 3)
        avg_bot = round(sum(bot_rates) / len(bot_rates), 1)
        nivel = max(group, key=lambda r: _nivel_rank(r["nivel_alerta"]))["nivel_alerta"]
        result.append({
            "ts": key,
            "score_global": avg_score,
            "bot_rate": avg_bot,
            "nivel_alerta": nivel,
            "total_ciclos": len(group),
            "dist_positivo": sum(r["dist_positivo"] for r in group),
            "dist_negativo": sum(r["dist_negativo"] for r in group),
            "dist_neutro": sum(r["dist_neutro"] for r in group),
        })
    return result


def get_stats_summary(hours: int = 24) -> dict:
    """Estadísticas agregadas del período: score medio, pico de bots, nivel más alto."""
    rows = get_history(hours=hours)
    if not rows:
        return {"sin_datos": True}
    scores = [r["score_global"] for r in rows]
    bot_rates = [r["bot_rate"] for r in rows]
    max_nivel = max(rows, key=lambda r: _nivel_rank(r["nivel_alerta"]))
    return {
        "ciclos": len(rows),
        "score_promedio": round(sum(scores) / len(scores), 3),
        "score_min": round(min(scores), 3),
        "score_max": round(max(scores), 3),
        "bot_rate_max": round(max(bot_rates), 1),
        "bot_rate_promedio": round(sum(bot_rates) / len(bot_rates), 1),
        "nivel_pico": max_nivel["nivel_alerta"],
        "nivel_pico_ts": max_nivel["ts"],
        "total_criticos": sum(r["alertas_criticas"] for r in rows),
        "total_bots_detectados": sum(r["bots_detectados"] for r in rows),
    }


def purge_old(days: int = 30) -> int:
    """Elimina registros más antiguos de N días. Devuelve cantidad eliminada."""
    try:
        conn = _get_conn()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cur = conn.execute("DELETE FROM sentiment_cycles WHERE ts < ?", (cutoff,))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        logger.info(f"[SENT-HIST] Purged {deleted} registros anteriores a {cutoff[:10]}")
        return deleted
    except Exception as e:
        logger.error(f"[SENT-HIST] Error purgando: {e}")
        return 0


def truncate_history(max_entries: int = 1000) -> int:
    """Mantiene solo los N ciclos más recientes. Elimina el exceso de los más antiguos."""
    try:
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM sentiment_cycles").fetchone()[0]
        if total <= max_entries:
            conn.close()
            return 0
        # Eliminar los más antiguos manteniendo max_entries
        cur = conn.execute("""
            DELETE FROM sentiment_cycles
            WHERE id NOT IN (
                SELECT id FROM sentiment_cycles
                ORDER BY ts DESC
                LIMIT ?
            )
        """, (max_entries,))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        logger.info(f"[SENT-HIST] Truncated {deleted} ciclos antiguos (limite: {max_entries})")
        return deleted
    except Exception as e:
        logger.error(f"[SENT-HIST] Error en truncate_history: {e}")
        return 0


# ── Cache de hashes de contenido (deduplicación) ──────────────────────────────

def hash_entry(entry: dict) -> str:
    """Genera hash de una entrada de noticias para deduplicación."""
    key = f"{entry.get('link','')}{entry.get('title','')}{entry.get('published','')}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def filter_new_entries(entries: list[dict]) -> list[dict]:
    """Filtra entradas ya procesadas según hash. Registra las nuevas."""
    if not entries:
        return []
    try:
        conn = _get_conn()
        # Calcular hashes
        hashed = [(e, hash_entry(e)) for e in entries]
        hashes = [h for _, h in hashed]

        existing_hashes = set()
        if hashes:
            # Batch checking to avoid loading the whole table or exceeding SQL variable limits
            chunk_size = 500
            for i in range(0, len(hashes), chunk_size):
                chunk = hashes[i:i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(f"SELECT hash FROM content_hash_cache WHERE hash IN ({placeholders})", chunk).fetchall()
                existing_hashes.update(r[0] for r in rows)

        new_entries = [e for e, h in hashed if h not in existing_hashes]
        new_hashes = [(h, datetime.now(timezone.utc).isoformat()) for _, h in hashed if h not in existing_hashes]
        if new_hashes:
            conn.executemany("INSERT OR IGNORE INTO content_hash_cache (hash, ts) VALUES (?,?)", new_hashes)
        # Purgar hashes viejos (>7 días) para no crecer indefinidamente
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        conn.execute("DELETE FROM content_hash_cache WHERE ts < ?", (cutoff,))
        conn.commit()
        conn.close()
        logger.debug(f"[SENT-HASH] {len(entries)} entradas → {len(new_entries)} nuevas para analizar")
        return new_entries
    except Exception as e:
        logger.error(f"[SENT-HASH] Error en filtrado: {e}")
        return entries  # fallback: analizar todo


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nivel_rank(nivel: str) -> int:
    return {"NORMAL": 0, "ATENCIÓN": 1, "ALERTA": 2, "BOT-STORM": 3, "CRÍTICO": 4}.get(nivel, 0)


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("top_palabras_pos", "top_palabras_neg", "narrativas_geo"):
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                d[key] = []
    return d
