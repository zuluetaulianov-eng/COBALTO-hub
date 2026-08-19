import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DB_FILE = Path(__file__).parent / "cobalto_cache.db"

_DB_URL = os.getenv("DATABASE_URL")
_USE_PG = bool(_DB_URL and "postgres" in _DB_URL)
if _USE_PG:
    _PG_URL = _DB_URL.replace("postgresql+asyncpg://", "postgresql://")

_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS sent_news (
    unique_id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS http_cache (
    source TEXT PRIMARY KEY,
    etag TEXT,
    last_modified TEXT,
    last_fetch DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'admin',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS card_notes (
    card_id TEXT NOT NULL,
    card_type TEXT DEFAULT 'news',
    note TEXT NOT NULL DEFAULT '',
    author TEXT DEFAULT 'operator',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (card_id, card_type)
);
CREATE TABLE IF NOT EXISTS operator_registry (
    operator_id TEXT PRIMARY KEY,
    operator_name TEXT NOT NULL,
    device_model TEXT DEFAULT '',
    unit_group TEXT DEFAULT 'ALPHA',
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS operator_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    altitude REAL DEFAULT 0,
    battery_level INTEGER DEFAULT 100,
    status TEXT DEFAULT 'PATROL',
    network_type TEXT DEFAULT '4G',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sent_news_ts ON sent_news(timestamp);
CREATE INDEX IF NOT EXISTS idx_op_telem_ts ON operator_telemetry(timestamp);
CREATE INDEX IF NOT EXISTS idx_op_telem_opid ON operator_telemetry(operator_id);
"""

_DDL_PG = """
CREATE TABLE IF NOT EXISTS sent_news (
    unique_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS http_cache (
    source TEXT PRIMARY KEY,
    etag TEXT,
    last_modified TEXT,
    last_fetch TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS card_notes (
    card_id TEXT NOT NULL,
    card_type TEXT DEFAULT 'news',
    note TEXT NOT NULL DEFAULT '',
    author TEXT DEFAULT 'operator',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (card_id, card_type)
);
CREATE TABLE IF NOT EXISTS operator_registry (
    operator_id TEXT PRIMARY KEY,
    operator_name TEXT NOT NULL,
    device_model TEXT DEFAULT '',
    unit_group TEXT DEFAULT 'ALPHA',
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS operator_telemetry (
    id SERIAL PRIMARY KEY,
    operator_id TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION DEFAULT 0,
    battery_level INTEGER DEFAULT 100,
    status TEXT DEFAULT 'PATROL',
    network_type TEXT DEFAULT '4G',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sent_news_ts ON sent_news(timestamp);
CREATE INDEX IF NOT EXISTS idx_op_telem_ts ON operator_telemetry(timestamp);
CREATE INDEX IF NOT EXISTS idx_op_telem_opid ON operator_telemetry(operator_id);
"""

class DBWrapper:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=()):
        if _USE_PG:
            query = query.replace("?", "%s")
            query = query.replace("datetime(timestamp) < datetime(%s)", "timestamp < %s::timestamp")

            if "INSERT OR IGNORE INTO sent_news" in query:
                query = query.replace("INSERT OR IGNORE INTO sent_news", "INSERT INTO sent_news")
                query += " ON CONFLICT (unique_id) DO NOTHING"
            elif "INSERT OR IGNORE INTO users" in query:
                query = query.replace("INSERT OR IGNORE INTO users", "INSERT INTO users")
                query += " ON CONFLICT (username) DO NOTHING"
            elif "ON CONFLICT(source) DO UPDATE SET" in query:
                query = query.replace("excluded.etag", "EXCLUDED.etag")
                query = query.replace("excluded.last_modified", "EXCLUDED.last_modified")
                query = query.replace("excluded.last_fetch", "EXCLUDED.last_fetch")
            elif "INSERT OR REPLACE INTO system_settings" in query:
                query = query.replace("INSERT OR REPLACE INTO system_settings", "INSERT INTO system_settings")
                query += " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at"

            cur = self.conn.cursor()
            cur.execute(query, params)
            return cur
        else:
            return self.conn.execute(query, params)

    def fetchone(self, query, params=()):
        cur = self.execute(query, params)
        return cur.fetchone()

    def fetchall(self, query, params=()):
        cur = self.execute(query, params)
        return cur.fetchall()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        self.close()

def get_connection() -> DBWrapper:
    if _USE_PG:
        import psycopg2
        from psycopg2.extras import DictCursor
        conn = psycopg2.connect(_PG_URL, cursor_factory=DictCursor)
        return DBWrapper(conn)
    else:
        conn = sqlite3.connect(str(DB_FILE), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return DBWrapper(conn)

_db_initialized = False

def init_db():
    global _db_initialized
    if _db_initialized:
        return
    try:
        if _USE_PG:
            import psycopg2
            conn = psycopg2.connect(_PG_URL)
            with conn.cursor() as cur:
                cur.execute(_DDL_PG)
            conn.commit()
            conn.close()
        else:
            conn = sqlite3.connect(str(DB_FILE), timeout=30)
            conn.executescript(_DDL_SQLITE)
            conn.commit()
            conn.close()

        # Insert or update admin password hash
        admin_user = os.getenv("ADMIN_USERNAME", "admin")
        admin_pass = os.getenv("ADMIN_PASSWORD", "admin")
        pass_hash = _hash_password(admin_pass)

        with get_connection() as conn:
            row = conn.fetchone("SELECT id FROM users WHERE username = ?", (admin_user,))
            if row:
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pass_hash, row[0]))
            else:
                conn.execute("INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)", (admin_user, pass_hash))

        _db_initialized = True
        logger.info("[DB] Base de datos principal inicializada (Capa B).")
    except Exception as e:
        logger.error(f"[DB] Error inicializando base de datos principal: {e}")

def ensure_db():
    if not _db_initialized:
        init_db()

# ---- TELEGRAM BOT CACHE FUNCIONES ----
def clean_old_sent_news(max_days=3):
    ensure_db()
    cutoff_date = datetime.now() - timedelta(days=max_days)
    cutoff_http = datetime.now() - timedelta(days=14)
    try:
        with get_connection() as conn:
            cur1 = conn.execute("DELETE FROM sent_news WHERE timestamp < ?", (cutoff_date.isoformat(),))
            deleted_sent = cur1.rowcount
            cur2 = conn.execute("DELETE FROM http_cache WHERE last_fetch < ?", (cutoff_http.isoformat(),))
            deleted_http = cur2.rowcount

            if deleted_sent > 0 or deleted_http > 0:
                logger.info(f"[DB] Limpieza: Eliminados {deleted_sent} sent_news y {deleted_http} http_cache.")
    except Exception as e:
        logger.error(f"[DB] Error limpiando caches: {e}")

def is_news_sent(unique_id):
    ensure_db()
    try:
        with get_connection() as conn:
            row = conn.fetchone("SELECT 1 FROM sent_news WHERE unique_id = ?", (unique_id,))
            return row is not None
    except Exception as e:
        logger.error(f"[DB] Error verificando cache de noticias: {e}")
        return False

def mark_news_sent(unique_id):
    ensure_db()
    try:
        with get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO sent_news (unique_id, timestamp) VALUES (?, ?)", (unique_id, datetime.now().isoformat()))
    except Exception as e:
        logger.error(f"[DB] Error marcando noticia: {e}")

# ---- EXTRACTOR CACHE FUNCIONES ----
def get_http_cache(source):
    ensure_db()
    try:
        with get_connection() as conn:
            row = conn.fetchone("SELECT etag, last_modified, last_fetch FROM http_cache WHERE source = ?", (source,))
            if row:
                # Soporta acceso por índice tanto en psycopg2 DictRow como en sqlite3.Row
                return {"etag": row[0], "last-modified": row[1], "last_fetch": row[2]}
    except Exception as e:
        logger.error(f"[DB] Error obteniendo http cache: {e}")
    return {}

def update_http_cache(source, etag, last_modified):
    ensure_db()
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO http_cache (source, etag, last_modified, last_fetch)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    etag = excluded.etag,
                    last_modified = excluded.last_modified,
                    last_fetch = excluded.last_fetch
            """, (source, etag, last_modified, datetime.now().isoformat()))
    except Exception as e:
        logger.error(f"[DB] Error actualizando http cache: {e}")

def get_all_http_cache():
    ensure_db()
    cache = {}
    try:
        with get_connection() as conn:
            for row in conn.fetchall("SELECT source, etag, last_modified, last_fetch FROM http_cache"):
                cache[row[0]] = {"etag": row[1], "last-modified": row[2], "last_fetch": row[3]}
    except Exception as e:
        logger.error(f"[DB] Error obteniendo todo el http cache: {e}")
    return cache

def _hash_password(password: str) -> str:
    """Hash con PBKDF2-HMAC-SHA256 + salt aleatorio (100k iteraciones)."""
    import secrets
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return f"{salt}${pwd_hash}"

def _check_password(password: str, stored: str) -> bool:
    """Verifica contraseña contra hash almacenado (formato salt$hash)."""
    if "$" not in stored:
        return False
    salt, expected = stored.split("$", 1)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return pwd_hash == expected

# ---- CAPA B: USERS & SETTINGS ----
def verify_user(username, password):
    ensure_db()
    admin_env_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_env_pass = os.getenv("ADMIN_PASSWORD")
    if admin_env_pass and username == admin_env_user and password == admin_env_pass:
        return True
    try:
        with get_connection() as conn:
            row = conn.fetchone("SELECT password_hash FROM users WHERE username = ?", (username,))
            if not row:
                return False
            stored_hash = row[0]
            if "$" in stored_hash:
                return _check_password(password, stored_hash)
            return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    except Exception as e:
        logger.error(f"[DB] Error verificando usuario: {e}")
    return False

def get_system_settings(key="dynamic_config"):
    ensure_db()
    try:
        with get_connection() as conn:
            row = conn.fetchone("SELECT value FROM system_settings WHERE key = ?", (key,))
            if row:
                return json.loads(row[0])
    except Exception as e:
        logger.error(f"[DB] Error obteniendo settings: {e}")
    return None

def save_system_settings(data, key="dynamic_config"):
    ensure_db()
    try:
        payload = json.dumps(data, ensure_ascii=False)
        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, payload, datetime.now().isoformat()))
        return True
    except Exception as e:
        logger.error(f"[DB] Error guardando settings: {e}")
        return False


# ---- MANTENIMIENTO: SOCIAL GRAPH CACHE ----
def clean_old_graph_cache(max_days: int = 7):
    """
    Purga entradas del grafo social más antiguas que max_days días.
    Intenta columnas 'created_at', 'timestamp' y 'fetched_at' por orden.
    Al finalizar ejecuta VACUUM para liberar espacio físico en disco.
    """
    graph_db_path = Path(__file__).parent / "social_graph_cache.db"
    if not graph_db_path.exists():
        return

    cutoff = (datetime.now() - timedelta(days=max_days)).isoformat()
    DATE_COLS = ("created_at", "timestamp", "fetched_at", "updated_at")
    total_deleted = 0

    try:
        conn = sqlite3.connect(str(graph_db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            for table in tables:
                # Obtener columnas reales de la tabla
                columns = {
                    row[1]
                    for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
                }
                for col in DATE_COLS:
                    if col in columns:
                        try:
                            cur = conn.execute(
                                f"DELETE FROM {table} WHERE {col} < ?", (cutoff,)
                            )
                            total_deleted += cur.rowcount
                        except sqlite3.OperationalError as e:
                            logger.warning(f"[DB GRAPH] Error purgando {table}.{col}: {e}")
                        break  # Solo purgar por la primera columna de fecha que exista

            conn.commit()
            conn.execute("VACUUM")
            logger.info(
                f"[DB GRAPH] Purga completada: {total_deleted} registros eliminados "
                f"(>{max_days} días) de social_graph_cache.db"
            )
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"[DB GRAPH] Error purgando social_graph_cache.db: {e}")


# ---- ANOTACIONES COLABORATIVAS ----
def save_note(card_id: str, card_type: str, note: str, author: str = "operator"):
    """Guarda o actualiza una nota para una card."""
    ensure_db()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO card_notes (card_id, card_type, note, author, updated_at) VALUES (?, ?, ?, ?, ?)",
                (card_id, card_type, note, author, datetime.now().isoformat()),
            )
        return True
    except Exception as e:
        logger.error(f"[NOTES] Error guardando nota: {e}")
        return False


def get_note(card_id: str, card_type: str = "news") -> dict:
    """Obtiene la nota de una card específica."""
    ensure_db()
    try:
        with get_connection() as conn:
            row = conn.fetchone(
                "SELECT note, author, updated_at FROM card_notes WHERE card_id = ? AND card_type = ?",
                (card_id, card_type),
            )
            if row:
                return {"card_id": card_id, "card_type": card_type, "note": row[0], "author": row[1], "updated_at": row[2]}
    except Exception as e:
        logger.error(f"[NOTES] Error leyendo nota: {e}")
    return {"card_id": card_id, "card_type": card_type, "note": "", "author": "", "updated_at": ""}


def get_all_notes() -> list:
    """Retorna todas las notas (para pre-cargar badges)."""
    ensure_db()
    try:
        with get_connection() as conn:
            rows = conn.fetchall("SELECT card_id, card_type, note, author, updated_at FROM card_notes ORDER BY updated_at DESC")
            return [{"card_id": r[0], "card_type": r[1], "note": r[2], "author": r[3], "updated_at": r[4]} for r in rows]
    except Exception as e:
        logger.error(f"[NOTES] Error listando notas: {e}")
        return []


# ---- TELEMETRÍA Y OPERADORES BFT ----
def register_or_update_operator(operator_id: str, operator_name: str, device_model: str = "", unit_group: str = "ALPHA") -> bool:
    """Registra o actualiza los datos de un operador de COBALTO Mobile."""
    ensure_db()
    try:
        with get_connection() as conn:
            row = conn.fetchone("SELECT operator_id FROM operator_registry WHERE operator_id = ?", (operator_id,))
            if row:
                conn.execute(
                    "UPDATE operator_registry SET operator_name = ?, device_model = ?, unit_group = ? WHERE operator_id = ?",
                    (operator_name, device_model, unit_group, operator_id)
                )
            else:
                conn.execute(
                    "INSERT INTO operator_registry (operator_id, operator_name, device_model, unit_group) VALUES (?, ?, ?, ?)",
                    (operator_id, operator_name, device_model, unit_group)
                )
        return True
    except Exception as e:
        logger.error(f"[BFT] Error registrando operador: {e}")
        return False


def save_operator_telemetry(operator_id: str, operator_name: str, lat: float, lon: float, altitude: float = 0, battery: int = 100, status: str = "PATROL", network: str = "4G", device_model: str = "", unit_group: str = "ALPHA") -> bool:
    """Guarda un latido de telemetría de un operador."""
    ensure_db()
    register_or_update_operator(operator_id, operator_name, device_model, unit_group)
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO operator_telemetry
                   (operator_id, latitude, longitude, altitude, battery_level, status, network_type, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (operator_id, float(lat), float(lon), float(altitude), int(battery), status, network, datetime.now().isoformat())
            )
        return True
    except Exception as e:
        logger.error(f"[BFT] Error guardando telemetría de operador {operator_id}: {e}")
        return False


def get_active_operators() -> list:
    """Retorna la lista de todos los operadores registrados con su última posición y telemetría."""
    ensure_db()
    try:
        with get_connection() as conn:
            sql = """
                SELECT r.operator_id, r.operator_name, r.device_model, r.unit_group, r.registered_at,
                       t.latitude, t.longitude, t.altitude, t.battery_level, t.status, t.network_type, t.timestamp
                FROM operator_registry r
                LEFT JOIN operator_telemetry t ON t.id = (
                    SELECT id FROM operator_telemetry
                    WHERE operator_id = r.operator_id
                    ORDER BY timestamp DESC LIMIT 1
                )
                ORDER BY t.timestamp DESC
            """
            rows = conn.fetchall(sql)
            operators = []
            for r in rows:
                operators.append({
                    "operator_id": r[0],
                    "operator_name": r[1],
                    "device_model": r[2] or "Dispositivo Móvil",
                    "unit_group": r[3] or "ALPHA",
                    "registered_at": str(r[4]),
                    "latitude": r[5] if r[5] is not None else 0.0,
                    "longitude": r[6] if r[6] is not None else 0.0,
                    "altitude": r[7] if r[7] is not None else 0.0,
                    "battery_level": r[8] if r[8] is not None else 100,
                    "status": r[9] or "PATROL",
                    "network_type": r[10] or "4G",
                    "last_seen_iso": str(r[11]) if r[11] is not None else str(r[4]),
                })
            return operators
    except Exception as e:
        logger.error(f"[BFT] Error obteniendo operadores activos: {e}")
        return []


def get_operator_trail(operator_id: str, limit: int = 50) -> list:
    """Retorna el histórico de coordenadas GPS de un operador."""
    ensure_db()
    try:
        with get_connection() as conn:
            rows = conn.fetchall(
                "SELECT latitude, longitude, altitude, battery_level, status, timestamp FROM operator_telemetry WHERE operator_id = ? ORDER BY timestamp DESC LIMIT ?",
                (operator_id, limit)
            )
            return [
                {
                    "latitude": r[0],
                    "longitude": r[1],
                    "altitude": r[2],
                    "battery_level": r[3],
                    "status": r[4],
                    "timestamp": str(r[5])
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"[BFT] Error obteniendo rastro de operador {operator_id}: {e}")
        return []

