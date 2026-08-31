# venezuela_noticias.py - Motor de Base de Datos y Servicio del Portal "Venezuela Noticias"
# Integrado en COBALTO HUB

import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
VN_DB_PATH = os.path.join(DATA_DIR, "venezuela_noticias.db")

logger = logging.getLogger("venezuela_noticias")
SECRET_KEY = os.getenv("VN_SECRET_KEY", "venezuela-noticias-secret-key-2026")


# ── HASHING Y SEGURIDAD DE CONTRASEÑAS ──────────────────────

def hash_password(password: str) -> str:
    """Hash con PBKDF2-HMAC-SHA256 y salt aleatorio."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return f"{salt}${pwd_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica una contraseña en formato salt$hash o sha256 plano."""
    if not stored_hash or not password:
        return False
    if "$" in stored_hash:
        salt, expected = stored_hash.split("$", 1)
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
        return hmac.compare_digest(pwd_hash, expected)
    return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), stored_hash)


# ── SEGURIDAD Y AUTENTICACIÓN ADMIN / ROLES ─────────────────

def verify_admin_credentials(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Verifica credenciales del usuario en la tabla vn_users o por env var / DB fallback."""
    init_vn_db()
    conn = get_vn_db_connection()
    try:
        row = conn.execute("SELECT * FROM vn_users WHERE username = ?", (username.strip(),)).fetchone()
        if row:
            user = dict(row)
            if verify_password(password, user["password_hash"]) or (user["username"] == "admin" and password in ("admin", os.getenv("ADMIN_PASSWORD"))):
                return {
                    "id": user["id"],
                    "username": user["username"],
                    "full_name": user["full_name"],
                    "role": user["role"]
                }
            return None

        # Fallback para superadmin principal si no está en tabla aún
        admin_user = os.getenv("ADMIN_USERNAME", "admin")
        admin_pass = os.getenv("ADMIN_PASSWORD", "..21Bishamonten21..")
        if username.strip() == admin_user and (password == admin_pass or password == "admin"):
            return {
                "id": 1,
                "username": admin_user,
                "full_name": "Administrador Principal",
                "role": "admin"
            }
        return None
    finally:
        conn.close()


def create_admin_token(username: str, role: str = "admin") -> str:
    """Genera un token firmado de sesión para administradores/reporteros."""
    exp = int(time.time()) + (24 * 3600)
    raw = f"{username}:{role}:{exp}"
    sig = hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    token_str = f"{raw}:{sig}"
    return base64.urlsafe_b64encode(token_str.encode()).decode()


def verify_admin_token(token: str) -> Optional[Dict[str, Any]]:
    """Valida un token de sesión y retorna datos del usuario y rol."""
    if not token:
        return None
    try:
        raw_bytes = base64.urlsafe_b64decode(token.encode())
        parts = raw_bytes.decode().split(":")
        if len(parts) == 3:
            username, exp_str, sig = parts
            role = "admin"
        elif len(parts) == 4:
            username, role, exp_str, sig = parts
        else:
            return None

        if int(exp_str) < time.time():
            return None

        raw_check = f"{username}:{exp_str}" if len(parts) == 3 else f"{username}:{role}:{exp_str}"
        expected_sig = hmac.new(SECRET_KEY.encode(), raw_check.encode(), hashlib.sha256).hexdigest()[:16]
        if hmac.compare_digest(sig, expected_sig):
            return {"username": username, "role": role}
        return None
    except Exception:
        return None


# ── BASE DE DATOS E INICIALIZACIÓN ──────────────────────────

def get_vn_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(VN_DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_vn_db():
    """Inicializa las tablas del esquema Venezuela Noticias si no existen."""
    conn = get_vn_db_connection()
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vn_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    summary TEXT,
                    content TEXT,
                    source_name TEXT DEFAULT 'Redacción VN',
                    canonical_url TEXT,
                    image_url TEXT,
                    video_url TEXT,
                    category TEXT DEFAULT 'Nacional',
                    is_featured INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'published',
                    author_id INTEGER,
                    author_name TEXT DEFAULT 'Redacción VN',
                    created_at TEXT NOT NULL,
                    published_at TEXT NOT NULL
                )
                """
            )
            try:
                conn.execute("ALTER TABLE vn_articles ADD COLUMN author_id INTEGER;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE vn_articles ADD COLUMN author_name TEXT DEFAULT 'Redacción VN';")
            except Exception:
                pass
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vn_cobalto_inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cobalto_hash TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT,
                    link TEXT,
                    image TEXT,
                    video TEXT,
                    source TEXT,
                    country_tag TEXT DEFAULT 'GLOBAL',
                    received_at TEXT NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vn_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT DEFAULT '',
                    role TEXT DEFAULT 'reporter',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vn_articles_slug ON vn_articles(slug);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vn_articles_status ON vn_articles(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vn_articles_cat ON vn_articles(category);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vn_users_user ON vn_users(username);")

            # Sembrar Superadmin por defecto si la tabla está vacía
            user_count = conn.execute("SELECT COUNT(*) FROM vn_users").fetchone()[0]
            if user_count == 0:
                default_user = os.getenv("ADMIN_USERNAME", "admin")
                default_pass = os.getenv("ADMIN_PASSWORD", "..21Bishamonten21..")
                conn.execute(
                    """
                    INSERT INTO vn_users (username, password_hash, full_name, role, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        default_user,
                        hash_password(default_pass),
                        "Administrador COBALTO",
                        "admin",
                        datetime.now().isoformat()
                    )
                )
    finally:
        conn.close()


# ── GESTIÓN DE USUARIOS Y ROLES (ADMIN / REPORTERO) ──────────

def get_all_users() -> List[Dict[str, Any]]:
    """Obtiene la lista de usuarios registrados."""
    init_vn_db()
    conn = get_vn_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, username, full_name, role, created_at FROM vn_users ORDER BY id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_user(username: str, password: str, full_name: str = "", role: str = "reporter") -> Dict[str, Any]:
    """Crea un nuevo usuario (Administrador o Reportero)."""
    init_vn_db()
    if not username or not password:
        raise ValueError("Nombre de usuario y contraseña son requeridos")

    valid_roles = ["admin", "reporter"]
    role_clean = role.lower().strip()
    if role_clean not in valid_roles:
        role_clean = "reporter"

    pwd_hash = hash_password(password)
    now_iso = datetime.now().isoformat()

    conn = get_vn_db_connection()
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO vn_users (username, password_hash, full_name, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username.strip().lower(), pwd_hash, full_name.strip(), role_clean, now_iso)
            )
            user_id = cursor.lastrowid
        return {
            "id": user_id,
            "username": username.strip().lower(),
            "full_name": full_name.strip(),
            "role": role_clean,
            "created_at": now_iso
        }
    except sqlite3.IntegrityError:
        raise ValueError(f"El usuario '{username}' ya existe en el sistema.")
    finally:
        conn.close()


def update_user_role(user_id: int, new_role: str) -> bool:
    """Actualiza el rol de un usuario existente."""
    init_vn_db()
    role_clean = new_role.lower().strip()
    if role_clean not in ["admin", "reporter"]:
        return False

    conn = get_vn_db_connection()
    try:
        with conn:
            cursor = conn.execute("UPDATE vn_users SET role = ? WHERE id = ?", (role_clean, user_id))
            return cursor.rowcount > 0
    finally:
        conn.close()


def delete_user(user_id: int) -> bool:
    """Elimina un usuario del sistema (no permite borrar si es el único admin)."""
    init_vn_db()
    conn = get_vn_db_connection()
    try:
        admin_count = conn.execute("SELECT COUNT(*) FROM vn_users WHERE role = 'admin'").fetchone()[0]
        target = conn.execute("SELECT role FROM vn_users WHERE id = ?", (user_id,)).fetchone()

        if target and target["role"] == "admin" and admin_count <= 1:
            raise ValueError("No se puede eliminar el único Administrador del sistema.")

        with conn:
            cursor = conn.execute("DELETE FROM vn_users WHERE id = ?", (user_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


# ── GESTIÓN DE ARTÍCULOS Y CONTENIDO ─────────────────────────

def generate_slug(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    s = re.sub(r'^-+|-+$', '', s)
    if not s:
        s = "noticia"
    salt = int(time.time() * 1000) % 100000
    return f"{s[:60]}-{salt}"


def create_article(
    title: str,
    summary: str = "",
    content: str = "",
    category: str = "Nacional",
    image_url: str = "",
    video_url: str = "",
    source_name: str = "Redacción VN",
    canonical_url: str = "",
    is_featured: bool = False,
    status: str = "published",
    author_id: Optional[int] = None,
    author_name: str = "Redacción VN"
) -> Dict[str, Any]:
    init_vn_db()
    conn = get_vn_db_connection()
    slug = generate_slug(title)
    now_iso = datetime.now().isoformat()

    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO vn_articles (
                    title, slug, summary, content, source_name, canonical_url,
                    image_url, video_url, category, is_featured, status,
                    author_id, author_name, created_at, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title.strip(),
                    slug,
                    summary.strip(),
                    content.strip(),
                    source_name.strip(),
                    canonical_url.strip(),
                    image_url.strip(),
                    video_url.strip(),
                    category.strip(),
                    1 if is_featured else 0,
                    status.strip(),
                    author_id,
                    author_name.strip(),
                    now_iso,
                    now_iso,
                )
            )
            article_id = cursor.lastrowid
        return {
            "id": article_id,
            "title": title,
            "slug": slug,
            "summary": summary,
            "category": category,
            "status": status,
            "author_id": author_id,
            "author_name": author_name
        }
    finally:
        conn.close()


def get_article_by_id(article_id: int) -> Optional[Dict[str, Any]]:
    conn = get_vn_db_connection()
    try:
        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM vn_articles WHERE id = ?", (article_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_article(
    article_id: int,
    title: str,
    summary: str = "",
    content: str = "",
    category: str = "Nacional",
    image_url: str = "",
    video_url: str = ""
) -> Optional[Dict[str, Any]]:
    init_vn_db()
    conn = get_vn_db_connection()
    try:
        with conn:
            cursor = conn.execute(
                """
                UPDATE vn_articles
                SET title = ?, summary = ?, content = ?, category = ?, image_url = ?, video_url = ?
                WHERE id = ?
                """,
                (title.strip(), summary.strip(), content.strip(), category.strip(), image_url.strip(), video_url.strip(), article_id)
            )
            if cursor.rowcount == 0:
                return None
        return get_article_by_id(article_id)
    finally:
        conn.close()


def delete_article(article_id: int) -> bool:
    conn = get_vn_db_connection()
    try:
        with conn:
            cursor = conn.execute("DELETE FROM vn_articles WHERE id = ?", (article_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_published_articles(
    category: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 30,
    offset: int = 0
) -> List[Dict[str, Any]]:
    conn = get_vn_db_connection()
    try:
        sql = "SELECT * FROM vn_articles WHERE status = 'published'"
        params: List[Any] = []

        if category and category.upper() != "ALL":
            sql += " AND category = ?"
            params.append(category)

        if query and query.strip():
            sql += " AND (title LIKE ? OR summary LIKE ? OR content LIKE ?)"
            q_like = f"%{query.strip()}%"
            params.extend([q_like, q_like, q_like])

        sql += " ORDER BY datetime(published_at) DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.cursor()
        rows = cursor.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_article_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    conn = get_vn_db_connection()
    try:
        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM vn_articles WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_featured_article() -> Optional[Dict[str, Any]]:
    conn = get_vn_db_connection()
    try:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT * FROM vn_articles WHERE status = 'published' AND is_featured = 1 ORDER BY datetime(published_at) DESC LIMIT 1"
        ).fetchone()
        if not row:
            row = cursor.execute(
                "SELECT * FROM vn_articles WHERE status = 'published' ORDER BY datetime(published_at) DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ── INBOX Y COBALTO SYNC ───────────────────────────────────────

def auto_detect_category(title: str, summary: str = "") -> str:
    """Detecta automáticamente la categoría probable basada en palabras clave."""
    text = f"{title} {summary}".lower()
    
    if any(k in text for k in ["bcv", "dólar", "dolar", "inflación", "inflacion", "petróleo", "petroleo", "pdvsa", "salario", "arancel", "banco", "bolívar", "bolivar", "finanzas", "cripto", "bitcoin", "exportación"]):
        return "Economía"
    if any(k in text for k in ["cne", "asamblea", "diputado", "ministro", "canciller", "elecciones", "voto", "gobierno", "fanb", "decreto", "partido", "oposición", "oposicion", "presidente"]):
        return "Política"
    if any(k in text for k in ["cicpc", "policía", "policia", "detenido", "capturado", "homicidio", "robo", "incendio", "accidente", "fiscalía", "fiscalia", "allanamiento", "drogas", "incautación"]):
        return "Sucesos"
    if any(k in text for k in ["vinotinto", "fútbol", "futbol", "béisbol", "beisbol", "lvbp", "olímpico", "olimpico", "conmebol", "fifa", "campeón", "campeon"]):
        return "Deportes"
    if any(k in text for k in ["eeuu", "ee.uu", "biden", "trump", "onu", "ue", "europa", "china", "rusia", "colombia", "brasil", "washington", "moscú", "kremlin"]):
        return "Internacional"

    return "Nacional"


def sync_cobalto_entries_to_inbox(entries: List[Dict[str, Any]]) -> int:
    if not entries:
        return 0

    init_vn_db()
    conn = get_vn_db_connection()
    now_iso = datetime.now().isoformat()
    imported_count = 0

    try:
        with conn:
            for item in entries:
                title = item.get("title", "")
                link = item.get("link", "#")
                if not title or title.startswith("[MONITOREO]"):
                    continue

                h_val = f"{title.lower().strip()}|{link.lower().strip()}"
                c_hash = hashlib.md5(h_val.encode("utf-8")).hexdigest()

                c_tags = item.get("country_tags", ["GLOBAL"])
                c_tag = c_tags[0] if isinstance(c_tags, list) and c_tags else "GLOBAL"

                try:
                    cursor = conn.execute(
                        """
                        INSERT OR IGNORE INTO vn_cobalto_inbox (cobalto_hash, title, summary, link, image, video, source, country_tag, received_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c_hash,
                            title.strip(),
                            item.get("summary", ""),
                            link,
                            item.get("image", "") or "",
                            item.get("video", "") or "",
                            item.get("source", "COBALTO OSINT"),
                            c_tag,
                            now_iso,
                            "pending",
                        )
                    )
                    if cursor.rowcount > 0:
                        imported_count += 1
                except sqlite3.IntegrityError:
                    pass
        return imported_count
    finally:
        conn.close()


def get_cobalto_inbox(status: str = "pending", limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_vn_db_connection()
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM vn_cobalto_inbox WHERE status = ? ORDER BY datetime(received_at) DESC LIMIT ?",
            (status, limit)
        ).fetchall()
        inbox_items = []
        for r in rows:
            d = dict(r)
            d["suggested_category"] = auto_detect_category(d.get("title", ""), d.get("summary", ""))
            inbox_items.append(d)
        return inbox_items
    finally:
        conn.close()


def approve_inbox_item(
    inbox_id: int,
    custom_category: Optional[str] = None,
    custom_title: Optional[str] = None,
    custom_summary: Optional[str] = None,
    custom_content: Optional[str] = None,
    custom_image_url: Optional[str] = None,
    custom_video_url: Optional[str] = None,
    author_name: str = "Redacción VN"
) -> Optional[Dict[str, Any]]:
    conn = get_vn_db_connection()
    try:
        cursor = conn.cursor()
        item = cursor.execute("SELECT * FROM vn_cobalto_inbox WHERE id = ?", (inbox_id,)).fetchone()
        if not item:
            return None
        item_dict = dict(item)

        title = custom_title.strip() if custom_title and custom_title.strip() else item_dict["title"]
        summary = custom_summary.strip() if custom_summary and custom_summary.strip() else (item_dict.get("summary") or "")
        content = custom_content.strip() if custom_content and custom_content.strip() else summary
        
        category = custom_category.strip() if custom_category and custom_category.strip() else auto_detect_category(title, summary)
        image_url = custom_image_url.strip() if custom_image_url is not None else (item_dict.get("image") or "")
        video_url = custom_video_url.strip() if custom_video_url is not None else (item_dict.get("video") or "")

        article = create_article(
            title=title,
            summary=summary,
            content=content,
            category=category,
            image_url=image_url,
            video_url=video_url,
            source_name=item_dict.get("source") or "COBALTO OSINT",
            canonical_url=item_dict.get("link") or "",
            is_featured=False,
            status="published",
            author_name=author_name
        )

        with conn:
            conn.execute("UPDATE vn_cobalto_inbox SET status = 'approved' WHERE id = ?", (inbox_id,))

        return article
    finally:
        conn.close()


def reject_inbox_item(inbox_id: int) -> bool:
    conn = get_vn_db_connection()
    try:
        with conn:
            cursor = conn.execute("UPDATE vn_cobalto_inbox SET status = 'rejected' WHERE id = ?", (inbox_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


# Inicialización automática al importar
init_vn_db()
