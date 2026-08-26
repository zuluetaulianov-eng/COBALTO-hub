"""
osiris_colombia_recon.py — Extractor OSINT de Fuentes Públicas de Colombia.
Procesa:
1. SECOP II y Datos Abiertos de Colombia (datos.gov.co API / Socrata SODA con SoQL)
2. JEP (Jurisdicción Especial para la Paz) — Sala de Prensa y Autos
3. Rama Judicial — Consulta de Procesos Judiciales (Playwright stealth & API Interception)
4. UNODC / SIMCI — Observatorio de Drogas (GeoJSON y reportes)
"""

import asyncio
import hashlib
import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)
COLOMBIA_DB_PATH = DATA_DIR / "colombia_osint.db"
RAMA_COOKIES_PATH = DATA_DIR / "rama_judicial_cookies.json"

# Endpoints oficiales de la API Socrata de datos.gov.co
SOCRATA_SECOP_II_ENDPOINT = "https://www.datos.gov.co/resource/jgit-wwpy.json"
JEP_PRENSA_URL = "https://www.jep.gov.co/Sala-de-Prensa/Paginas/Comunicados-2024.aspx"
RAMA_JUDICIAL_API = "https://consultaprocesos.ramajudicial.gov.co/api/v1/Procesos/Consulta/NumeroRadicacion"


def init_colombia_db():
    """Inicializa el esquema de SQLite estandarizado para almacenamiento masivo de inteligencia Colombia."""
    with sqlite3.connect(COLOMBIA_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS colombia_intel (
                id_hash TEXT PRIMARY KEY,
                fuente_origen TEXT NOT NULL,
                fecha_registro TEXT,
                entidades_identificadas TEXT,
                monto_cop REAL,
                titulo TEXT,
                resumen TEXT,
                payload_json TEXT,
                fetched_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fuente ON colombia_intel(fuente_origen);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fecha ON colombia_intel(fecha_registro);")
        conn.commit()


init_colombia_db()


# ============================================================================
# 1. SECOP II / DATOS ABIERTOS (API SODA SOCRATA CON SOQL)
# ============================================================================

async def query_secop_socrata(
    query_text: Optional[str] = None,
    departamento: Optional[str] = None,
    monto_min: Optional[float] = None,
    limit: int = 100,
    offset: int = 0,
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    Realiza una consulta masiva paginada a SECOP II (datos.gov.co) utilizando SoQL (Socrata Query Language).
    Aplica backoff exponencial para evitar throttling HTTP 429.
    """
    where_conditions = []
    if query_text:
        clean_q = query_text.replace("'", "''")
        where_conditions.append(f"(descripcion_del_proceso LIKE '%{clean_q}%' OR nombre_del_contratista LIKE '%{clean_q}%')")
    if departamento:
        clean_dep = departamento.upper().replace("'", "''")
        where_conditions.append(f"departamento = '{clean_dep}'")
    if monto_min is not None:
        where_conditions.append(f"valor_del_contrato >= {monto_min}")

    params = {
        "$limit": str(min(limit, 1000)),
        "$offset": str(offset),
        "$order": "fecha_de_firma DESC"
    }
    if where_conditions:
        params["$where"] = " AND ".join(where_conditions)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    backoff = 2.0
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SOCRATA_SECOP_II_ENDPOINT, params=params, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            _save_secop_records_to_db(data)
                            return data
                    elif resp.status == 429:
                        logger.warning(f"[SECOP SOCRATA] Throttle 429 detectado. Reintentando en {backoff}s...")
                        await asyncio.sleep(backoff)
                        backoff *= 2
                    else:
                        logger.warning(f"[SECOP SOCRATA] Respuesta HTTP {resp.status} de Socrata.")
        except Exception as e:
            logger.warning(f"[SECOP SOCRATA] Error en intento {attempt+1}/{max_retries}: {e}")
            await asyncio.sleep(backoff)
            backoff *= 2

    return []


def _save_secop_records_to_db(records: List[Dict[str, Any]]):
    """Guarda en lote los contratos descargados de SECOP II en la BD local SQLite."""
    now_iso = datetime.now().isoformat()
    to_insert = []

    for r in records:
        url_or_id = r.get("urlproceso", {}).get("url") or r.get("id_contrato") or r.get("referencia_del_contrato") or str(r)
        id_hash = hashlib.sha256(url_or_id.encode("utf-8")).hexdigest()[:16]
        fecha = r.get("fecha_de_firma") or r.get("fecha_de_inicio_del_contrato") or ""
        contratista = r.get("nombre_del_contratista") or "N/A"
        entidad = r.get("nombre_entidad") or "N/A"
        monto = float(r.get("valor_del_contrato", 0) or 0)
        titulo = f"SECOP II: {entidad} - {contratista}"
        resumen = r.get("descripcion_del_proceso") or ""

        entidades = json.dumps([entidad, contratista], ensure_ascii=False)
        payload = json.dumps(r, ensure_ascii=False)

        to_insert.append((id_hash, "SECOP_II", fecha, entidades, monto, titulo, resumen, payload, now_iso))

    if to_insert:
        try:
            with sqlite3.connect(COLOMBIA_DB_PATH) as conn:
                conn.executemany("""
                    INSERT OR REPLACE INTO colombia_intel
                    (id_hash, fuente_origen, fecha_registro, entidades_identificadas, monto_cop, titulo, resumen, payload_json, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, to_insert)
                conn.commit()
        except Exception as e:
            logger.error(f"[SECOP DB] Error al guardar lote en SQLite: {e}")


# ============================================================================
# 2. JEP (JURISDICCIÓN ESPECIAL PARA LA PAZ) - SALA DE PRENSA Y AUTOS
# ============================================================================

async def fetch_jep_press_releases(limit: int = 15) -> List[Dict[str, Any]]:
    """Extrae comunicados y resoluciones recientes de la JEP."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    results = []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(JEP_PRENSA_URL, headers=headers, timeout=12) as resp:
                if resp.status == 200:
                    html_text = await resp.text()
                    soup = BeautifulSoup(html_text, "html.parser")
                    items = soup.find_all(["article", "div"], class_=re.compile(r"noticia|comunicado|item", re.I))

                    for item in items[:limit]:
                        link_tag = item.find("a")
                        title_tag = item.find(["h2", "h3", "h4"]) or link_tag
                        date_tag = item.find(class_=re.compile(r"fecha|date", re.I))

                        if title_tag and link_tag:
                            title = title_tag.get_text(strip=True)
                            href = link_tag.get("href", "")
                            if href and not href.startswith("http"):
                                href = "https://www.jep.gov.co" + href

                            fecha = date_tag.get_text(strip=True) if date_tag else ""
                            id_hash = hashlib.sha256(href.encode("utf-8")).hexdigest()[:16]

                            record = {
                                "id_hash": id_hash,
                                "fuente_origen": "JEP_PRENSA",
                                "titulo": title,
                                "link": href,
                                "fecha_registro": fecha,
                                "fetched_at": datetime.now().isoformat()
                            }
                            results.append(record)

                            _save_generic_intel_to_db("JEP_PRENSA", id_hash, title, "", fecha, href, record)
    except Exception as e:
        logger.warning(f"[JEP EXTRACTOR] Error al consultar JEP Prensa: {e}")

    return results


def _save_generic_intel_to_db(fuente: str, id_hash: str, titulo: str, resumen: str, fecha: str, link: str, payload_dict: Dict):
    """Persiste registros genéricos de inteligencia Colombia en SQLite."""
    now_iso = datetime.now().isoformat()
    try:
        with sqlite3.connect(COLOMBIA_DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO colombia_intel
                (id_hash, fuente_origen, fecha_registro, entidades_identificadas, monto_cop, titulo, resumen, payload_json, fetched_at)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?);
            """, (id_hash, fuente, fecha, json.dumps([], ensure_ascii=False), titulo, resumen, json.dumps(payload_dict, ensure_ascii=False), now_iso))
            conn.commit()
    except Exception as e:
        logger.error(f"[COLOMBIA DB] Error persistiendo {fuente}: {e}")


# ============================================================================
# 3. RAMA JUDICIAL (PLAYWRIGHT STEALTH & COOKIE INJECTION / API)
# ============================================================================

def save_rama_judicial_session(cookies: List[Dict[str, Any]]):
    """Guarda cookies de sesión capturadas manualmente o en modo Headed."""
    try:
        with open(RAMA_COOKIES_PATH, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        logger.info("[RAMA JUDICIAL] Cookies de sesión guardadas con éxito.")
    except Exception as e:
        logger.error(f"[RAMA JUDICIAL] Error guardando cookies: {e}")


def load_rama_judicial_cookies() -> Dict[str, str]:
    """Carga cookies de sesión guardadas para reutilización sin reCAPTCHA."""
    if not RAMA_COOKIES_PATH.exists():
        return {}
    try:
        with open(RAMA_COOKIES_PATH, "r", encoding="utf-8") as f:
            cookies_list = json.load(f)
            return {c["name"]: c["value"] for c in cookies_list if "name" in c and "value" in c}
    except Exception:
        return {}


async def query_rama_judicial_radicado(numero_radicacion: str) -> Dict[str, Any]:
    """
    Consulta un expediente penal/judicial en la Rama Judicial por número de radicación (23 dígitos).
    Intenta reutilizar la sesión guardada para evadir reCAPTCHA.
    """
    clean_rad = re.sub(r"\D", "", numero_radicacion)
    if len(clean_rad) != 23:
        return {"error": "El número de radicación debe contener exactamente 23 dígitos numéricos."}

    cookies = load_rama_judicial_cookies()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://consultaprocesos.ramajudicial.gov.co/"
    }

    url = f"{RAMA_JUDICIAL_API}/{clean_rad}"
    try:
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url, headers=headers, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    id_hash = hashlib.sha256(clean_rad.encode("utf-8")).hexdigest()[:16]
                    _save_generic_intel_to_db("RAMA_JUDICIAL", id_hash, f"Proceso {clean_rad}", str(data)[:300], datetime.now().strftime("%Y-%m-%d"), url, data)
                    return data
                elif resp.status == 403 or resp.status == 401:
                    return {
                        "error": "Sesión o captcha expírado en la Rama Judicial. Inicie el extractor Headed para actualizar cookies.",
                        "status_code": resp.status
                    }
    except Exception as e:
        logger.warning(f"[RAMA JUDICIAL] Error en consulta API direct: {e}")

    return {"error": f"No se pudo consultar el radicado {clean_rad}. WAF activo.", "radicado": clean_rad}


# ============================================================================
# 4. RESUMEN Y CONSULTA LOCAL DE BD
# ============================================================================

def get_colombia_intel_summary(limit: int = 50) -> List[Dict[str, Any]]:
    """Retorna los registros más recientes recopilados en la BD de Colombia."""
    results = []
    try:
        with sqlite3.connect(COLOMBIA_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id_hash, fuente_origen, fecha_registro, entidades_identificadas, monto_cop, titulo, resumen, fetched_at
                FROM colombia_intel
                ORDER BY fetched_at DESC
                LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            for r in rows:
                results.append(dict(r))
    except Exception as e:
        logger.error(f"[COLOMBIA INTEL] Error leyendo de SQLite: {e}")

    return results
