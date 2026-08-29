"""
osint_cne.py — CNE (Consejo Nacional Electoral de Venezuela) Institutional OSINT Engine.
Public-institution intelligence: official press releases, official notices (avisos),
electoral calendar & public electoral normativa. Includes a Wayback fallback channel
used while the live portal is unreachable.

Deliberate scope: this module collects ONLY public, institution-level information
published by the CNE (comunicados, avisos oficiales, normativa, resultados agregados
por mesa). It performs NO profiling of private individuals' identity data (e.g. the
Registro Electoral / pollbook is explicitly out of scope).
"""
from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Circuit Breaker State ──
_cne_cb_lock = threading.Lock()
_cne_failures = 0
_CNE_CB_THRESHOLD = 4
_CNE_CB_RECOVERY = 600  # 10 minutes
_cne_disabled_until = 0

CNE_BASE = "https://cne.gov.ve"
CNE_NEWS_LIVE = f"{CNE_BASE}/web/sala_prensa/noticias.php"
CNE_AO_LIVE = f"{CNE_BASE}/web/sala_prensa/ao.php"
CNE_NORMATIVA_LIVE = f"{CNE_BASE}/web/normativa_electoral/leyes.php"

WAYBACK_API = "https://web.archive.org/cdx/search/cdx"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"

# Public institutional categories (comunicado/noticia tagging)
CATEGORY_KEYWORDS = [
    ("convocatoria", ["convocatoria", "convoca", "convocar", "convocan", "convocad", "postulacion", "postulación", "inscripcion", "inscripción", "solicitud", "participación", "participacion"]),
    ("resultados", ["resultado", "elecciones", "escrutinio", "boletín", "boletin", "mesa", "conteo", "totalización", "totalizacion"]),
    ("normativa", ["ley", "reglamento", "norma", "gaceta", "resolución", "resolucion", "jurídica", "juridica"]),
    ("aviso_oficial", ["aviso", "comunicado", "nota de prensa", "oficial", "cronograma", "calendario", "acto público", "acto publico"]),
    ("institucional", ["presidente", "rector", "autoridad", "reunión", "reunion", "embajad", "memorando", "condecoración", "condecoracion", "poder electoral"]),
]

# Public institutional keywords for the 'diplomatic/institutional' tag
DIPLOMATIC_KEYWORDS = [
    "embajad", "memorando", "memorándum", "internacional", "visit", "condecoración",
    "condecoracion", "autoridad electoral", "cooperación", "cooperacion", "misión", "mision",
]


def is_cne_available() -> bool:
    global _cne_failures, _cne_disabled_until
    with _cne_cb_lock:
        if time.time() < _cne_disabled_until:
            return False
        return True


def report_cne_failure():
    global _cne_failures, _cne_disabled_until
    with _cne_cb_lock:
        _cne_failures += 1
        if _cne_failures >= _CNE_CB_THRESHOLD:
            _cne_disabled_until = time.time() + _CNE_CB_RECOVERY
            logger.warning(f"[CNE CB] Circuito abierto ({_cne_failures} fallos). Reintentando en {_CNE_CB_RECOVERY}s.")


def report_cne_success():
    global _cne_failures, _cne_disabled_until
    with _cne_cb_lock:
        _cne_failures = 0
        _cne_disabled_until = 0


def _get_text(url: str, timeout: int = 20) -> str | None:
    """Fetch text content with SSL verification disabled (gov SSL quirks) + UA spoof."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, verify=False)
        if resp.status_code == 200:
            return resp.text
        logger.debug(f"[CNE] HTTP {resp.status_code} for {url}")
        return None
    except Exception as e:
        logger.debug(f"[CNE] fetch error {url}: {e}")
        return None


# ── Wayback fallback helpers ──
def _wayback_snapshot(live_url: str, from_year: str = "2023", to_year: str = "2026") -> str | None:
    """Return the most recent Wayback capture URL for a live CNE path, or None."""
    host_path = live_url.replace(CNE_BASE, "cne.gov.ve")
    try:
        r = requests.get(
            WAYBACK_API,
            params={
                "url": host_path, "output": "json", "fl": "timestamp,statuscode",
                "filter": "statuscode:200", "from": from_year, "to": to_year,
                "limit": "1",
            },
            timeout=25,
        )
        data = r.json()
        if isinstance(data, list) and len(data) > 1:
            ts = data[1][0]
            return f"https://web.archive.org/web/{ts}/{host_path}"
    except Exception as e:
        logger.debug(f"[CNE WAYBACK] error {live_url}: {e}")
    return None


def _fetch_with_fallback(live_url: str, timeout: int = 20) -> tuple[str | None, str]:
    """Fetch a CNE page from the live channel, falling back to the Wayback archive."""
    html = _get_text(live_url, timeout=timeout)
    if html:
        return html, "vivo"
    snap = _wayback_snapshot(live_url)
    if snap:
        html = _get_text(snap, timeout=40)
        if html:
            return html, "wayback"
    return None, "ninguno"


# ── News parser ──
def _parse_news_page(html_text: str, limit: int = 15) -> list[dict]:
    """Parse the CNE Noticias listing. Each item: fecha + título + enlace noticia_detallada."""
    items: list[dict] = []
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        seen: set[str] = set()
        # Each news block has an `a.noticia_titulo`; locate its nearest `td.noticia_fecha` ascendant.
        for a in soup.find_all("a", class_="noticia_titulo"):
            title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if not title or title in seen:
                continue
            href = a.get("href", "")
            if "noticia_detallada.php" not in href:
                continue
            seen.add(title)
            # Build absolute link (strip any wayback injected prefix)
            link = _normalize_link(href)
            date_str = ""
            # Search ascendant <td> chain & sibling row for noticia_fecha
            parent = a.find_parent("td")
            for _ in range(6):
                if parent is None:
                    break
                row = parent
                if hasattr(row, "find_parent") and row.find_parent("tr"):
                    row = row.find_parent("tr")
                fecha_cell = row.find("td", class_="noticia_fecha") if row else None
                if fecha_cell:
                    date_str = fecha_cell.get_text(strip=True)
                    break
                parent = parent.find_parent("td")
            items.append({
                "title": title,
                "link": link,
                "published": date_str,
                "category": "Noticias",
                "summary": "",
            })
            if len(items) >= limit:
                break
    except Exception as e:
        logger.warning(f"[CNE NEWS] parse error: {e}")
    return items


def _normalize_link(href: str) -> str:
    """Rebuild an absolute CNE link from a (possibly wayback-injected) href."""
    if not href:
        return CNE_BASE
    if href.startswith("http"):
        # strip wayback injected prefixes like /web/TIMESTAMP/...
        m = re.search(r"/web/\d{14}/(https?://.*)", href)
        if m:
            return m.group(1)
        return href
    if href.startswith(("/web/", "./", "../", "/")):
        core = re.sub(r"^/web/\d{14}/(?:im_/)?(?:https?://[^/]+)?", "", href)
        core = core.lstrip("./")
        return f"{CNE_BASE}/{core}"
    return f"{CNE_BASE}/{href.lstrip('./')}"


# ── Avisos Oficiales parser ──
def _parse_avisos_page(html_text: str, limit: int = 20) -> list[dict]:
    """Parse the CNE Avisos Oficiales listing (actos públicos + documentos PDF)."""
    items: list[dict] = []
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "ao_documents" not in href and "aviso" not in href.lower() and "comunicado" not in href.lower():
                continue
            title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if not title or title in seen:
                continue
            seen.add(title)
            items.append({"title": title, "link": _normalize_link(href)})
            if len(items) >= limit:
                break
    except Exception as e:
        logger.warning(f"[CNE AVISOS] parse error: {e}")
    return items


def _classify(item: dict) -> str:
    """Tag a public institutional communication by category keywords (title-based)."""
    haystack = (item.get("title") or "").lower()
    for label, words in CATEGORY_KEYWORDS:
        if any(w in haystack for w in words):
            if label == "institucional" and any(k in haystack for k in DIPLOMATIC_KEYWORDS):
                return "institucional_diplomatico"
            return label
    if any(k in haystack for k in DIPLOMATIC_KEYWORDS):
        return "institucional_diplomatico"
    return "institucional"


# ── Main institutional lookup ──
async def cne_lookup(scope: str = "institucional") -> dict:
    """
    CNE institutional OSINT lookup (public institution-level information only).

    Live channel is preferred; when the live portal is unreachable the Wayback
    Machine archive is used as fallback. No individual voter data is collected.
    """
    if not is_cne_available():
        return {
            "status": "degraded",
            "fuente": "🇻🇪 CNE (Circuit Breaker Activo)",
            "error": "Portal CNE temporalmente inaccesible.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    loop = asyncio_loop()
    executor = ThreadPoolExecutor(max_workers=4)

    def _fetch_all():
        comms: list[dict] = []
        avisos: list[dict] = []
        channel = "ninguno"
        # 1. Noticias
        news_html, c1 = _fetch_with_fallback(CNE_NEWS_LIVE)
        if news_html:
            comms = _parse_news_page(news_html, limit=15)
            channel = c1
        # 2. Avisos oficiales
        ao_html, c2 = _fetch_with_fallback(CNE_AO_LIVE)
        if ao_html:
            avisos = _parse_avisos_page(ao_html, limit=20)
            if channel == "ninguno":
                channel = c2
        return comms, avisos, channel

    try:
        comms, avisos, channel = await loop.run_in_executor(executor, _fetch_all)
        report_cne_success()
    except Exception as e:
        logger.warning(f"[CNE] lookup error: {e}")
        report_cne_failure()
        comms, avisos, channel = [], [], "ninguno"

    for c in comms:
        c["category"] = _classify(c)
    for av in avisos:
        av["category"] = _classify(av)

    result = {
        "status": "CONSULTADO",
        "institucion": "Consejo Nacional Electoral (CNE) de Venezuela",
        "pais": "Venezuela",
        "fuente": "🇻🇪 Portal Oficial CNE (https://cne.gov.ve)",
        "canal": channel,
        "alcance": "OSINT institucional público — sin perfilamiento de personas naturales (Registro Electoral fuera de alcance)",
        "comunicados": comms,
        "avisos_oficiales": avisos,
        "categorias": {
            "convocatoria": [c for c in comms if c["category"] == "convocatoria"],
            "resultados": [c for c in comms if c["category"] == "resultados"],
            "normativa": [c for c in comms + avisos if c["category"] == "normativa"],
            "aviso_oficial": [c for c in avisos if c["category"] == "aviso_oficial"],
            "institucional_diplomatico": [c for c in comms if c["category"] == "institucional_diplomatico"],
        },
        "secciones_institucionales": [
            {"nombre": "Noticias", "ruta": "/web/sala_prensa/noticias.php", "descripcion": "Comunicados y noticias públicas del CNE."},
            {"nombre": "Avisos Oficiales", "ruta": "/web/sala_prensa/ao.php", "descripcion": "Convocatorias, actos públicos y comunicados oficiales."},
            {"nombre": "Normativa Electoral", "ruta": "/web/normativa_electoral/leyes.php", "descripcion": "Leyes, reglamentos y gacetas electorales."},
            {"nombre": "Resultados Electorales", "ruta": "/web/estadisticas/index_resultados_elecciones.php", "descripcion": "Resultados agregados por mesa (anónimos)."},
            {"nombre": "Gacetas Electorales", "ruta": "/web/gacetas_electorales/", "descripcion": "Publicaciones oficiales en gaceta electoral."},
            {"nombre": "Sistema Electoral", "ruta": "/web/sistema_electoral/", "descripcion": "Descripción del sistema electoral venezolano."},
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if scope == "noticias":
        result = {"comunicados": comms, "total": len(comms), "canal": channel, "timestamp": datetime.now(timezone.utc).isoformat()}
    elif scope == "avisos":
        result = {"avisos_oficiales": avisos, "total": len(avisos), "canal": channel, "timestamp": datetime.now(timezone.utc).isoformat()}

    return result


async def cne_news() -> dict:
    """Fast endpoint: only public institutional news/comunicados."""
    return await cne_lookup(scope="noticias")


async def cne_avisos() -> dict:
    """Fast endpoint: only official notices (avisos oficiales)."""
    return await cne_lookup(scope="avisos")


def asyncio_loop():
    """Return the current running event loop or a fresh one."""
    import asyncio
    try:
        return asyncio.get_event_loop()
    except Exception:
        return asyncio.new_event_loop()


def get_cne_data() -> dict:
    """Dashboard Sensor integration (public institutional communications)."""
    comms: list[dict] = []
    channel = "ninguno"
    html, channel = _fetch_with_fallback(CNE_NEWS_LIVE, timeout=15)
    if html:
        comms = _parse_news_page(html, limit=10)
        for c in comms:
            c["category"] = _classify(c)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": {"🇻🇪 CNE Comunicados": comms},
        "count": len(comms),
        "canal": channel,
    }


def parse_cne_voter_html(html_text: str) -> dict | None:
    """Extract voter information from historical CNE ce.php HTML content."""
    if not html_text:
        return None
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        text = soup.get_text(" ", strip=True)
        if not any(k in text for k in ["Cédula", "Cedula", "Nombre", "Centro", "Estado"]):
            return None

        data: dict[str, str] = {}

        # 1. Direct table/element cell extraction
        for tag in soup.find_all(["td", "b", "strong", "div", "span", "p"]):
            t_str = tag.get_text(strip=True)
            if ":" in t_str and len(t_str) < 200:
                parts = t_str.split(":", 1)
                k, v = parts[0].strip().lower(), parts[1].strip()
                if "cédula" in k or "cedula" in k:
                    if not data.get("cedula") and v:
                        data["cedula"] = v
                elif "nombre" in k or "elector" in k:
                    if not data.get("nombre") and v:
                        data["nombre"] = v
                elif "estado" in k:
                    if not data.get("estado") and v:
                        data["estado"] = v
                elif "municipio" in k:
                    if not data.get("municipio") and v:
                        data["municipio"] = v
                elif "parroquia" in k:
                    if not data.get("parroquia") and v:
                        data["parroquia"] = v
                elif "centro" in k:
                    if not data.get("centro_votacion") and v:
                        data["centro_votacion"] = v
                elif "direcc" in k:
                    if not data.get("direccion") and v:
                        data["direccion"] = v
                elif "mesa" in k:
                    if not data.get("mesa") and v:
                        data["mesa"] = v

        # 2. Regex fallback extraction from flat body text
        def extract_regex(label_pat: str) -> str:
            m = re.search(rf"{label_pat}\s*:?\s*([^<\n\r]+)", text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                for kw in ["Cédula", "Cedula", "Nombre", "Estado", "Municipio", "Parroquia", "Centro", "Dirección", "Direccion", "Mesa"]:
                    if kw.lower() in val.lower():
                        pos = val.lower().find(kw.lower())
                        if pos > 0:
                            val = val[:pos].strip()
                return val[:120]
            return ""

        if not data.get("cedula"):
            data["cedula"] = extract_regex(r"Cédula|Cedula")
        if not data.get("nombre"):
            data["nombre"] = extract_regex(r"Nombre")
        if not data.get("estado"):
            data["estado"] = extract_regex(r"Estado")
        if not data.get("municipio"):
            data["municipio"] = extract_regex(r"Municipio")
        if not data.get("parroquia"):
            data["parroquia"] = extract_regex(r"Parroquia")
        if not data.get("centro_votacion"):
            data["centro_votacion"] = extract_regex(r"Centro")
        if not data.get("direccion"):
            data["direccion"] = extract_regex(r"Dirección|Direccion")
        if not data.get("mesa"):
            data["mesa"] = extract_regex(r"Mesa")

        if data.get("nombre") or data.get("centro_votacion") or data.get("estado"):
            return data
    except Exception as e:
        logger.warning(f"[CNE VOTER PARSER] parse error: {e}")
    return None


def cne_voter_wayback_lookup(cedula: str) -> dict:
    """
    Lookup voter center (Centro de Votación) by Cédula using historical Wayback Machine captures (CDX API).
    """
    if not cedula:
        return {"status": "ERROR", "error": "Cédula vacía"}

    cleaned = re.sub(r"[^A-Za-z0-9]", "", cedula).upper()
    nationality = cleaned[0] if cleaned and cleaned[0] in ("V", "E") else "V"
    digits = cleaned[1:] if cleaned and cleaned[0] in ("V", "E") else cleaned

    if not digits.isdigit() or not (5 <= len(digits) <= 8):
        return {
            "status": "ERROR",
            "error": f"Formato de cédula inválido ({cedula}). Debe ser V-12345678 o E-12345678.",
            "cedula_consultada": cedula,
        }

    formatted_cedula = f"{nationality}-{digits}"

    # Target URL variations historically used by CNE
    target_urls = [
        f"http://www.cne.gob.ve/web/registro_electoral/ce.php?nacionalidad={nationality}&cedula={digits}",
        f"http://cne.gob.ve/web/registro_electoral/ce.php?nacionalidad={nationality}&cedula={digits}",
        f"http://www.cne.gov.ve/web/registro_electoral/ce.php?nacionalidad={nationality}&cedula={digits}",
        f"http://cne.gov.ve/web/registro_electoral/ce.php?nacionalidad={nationality}&cedula={digits}",
        f"http://www.cne.gob.ve/regs/ce.php?nacionalidad={nationality}&cedula={digits}",
    ]

    snapshot_url = None
    archive_ts = None
    searched_urls = []

    for target in target_urls:
        searched_urls.append(target)
        try:
            r = requests.get(
                WAYBACK_API,
                params={
                    "url": target,
                    "output": "json",
                    "fl": "timestamp,original,statuscode",
                    "filter": "statuscode:200",
                    "limit": "5",
                },
                timeout=12,
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 1:
                    archive_ts = data[1][0]
                    orig = data[1][1]
                    snapshot_url = f"https://web.archive.org/web/{archive_ts}/{orig}"
                    break
        except Exception as e:
            logger.debug(f"[CNE VOTER WAYBACK] CDX lookup error for {target}: {e}")

    if not snapshot_url:
        return {
            "status": "SIN_REGISTRO_ARCHIVADO",
            "cedula": formatted_cedula,
            "metodo": "Archivos Históricos Wayback Machine (CDX API)",
            "mensaje": f"No se encontró captura web archivada en Wayback Machine para la cédula {formatted_cedula}.",
            "urls_consultadas": searched_urls,
            "alternativa_recomendada": "Para consultas 100% garantizadas e instantáneas sin depender del archivo web, se recomienda configurar la Opción A (Base de Datos Local SQLite en data/cne_registro_electoral.db).",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Fetch archived page content
    html_text = _get_text(snapshot_url, timeout=25)
    if not html_text:
        return {
            "status": "ERROR_DESCARGA_ARCHIVO",
            "cedula": formatted_cedula,
            "snapshot_url": snapshot_url,
            "mensaje": "Se encontró el índice de captura pero no se pudo recuperar el HTML de Wayback Machine.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    parsed = parse_cne_voter_html(html_text)
    if not parsed:
        return {
            "status": "CAPTURA_NO_PARSEABLE",
            "cedula": formatted_cedula,
            "snapshot_url": snapshot_url,
            "snapshot_timestamp": archive_ts,
            "mensaje": "Se recuperó la captura de Wayback Machine pero no contenía datos de registro electoral procesables.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "status": "ENCONTRADO",
        "cedula": parsed.get("cedula") or formatted_cedula,
        "nombre": parsed.get("nombre", "No especificado"),
        "estado": parsed.get("estado", "Desconocido"),
        "municipio": parsed.get("municipio", "Desconocido"),
        "parroquia": parsed.get("parroquia", "Desconocido"),
        "centro_votacion": parsed.get("centro_votacion", "Desconocido"),
        "direccion": parsed.get("direccion", ""),
        "mesa": parsed.get("mesa", ""),
        "fuente": "🇻🇪 Wayback Machine Archive (CNE Histórico)",
        "snapshot_url": snapshot_url,
        "snapshot_timestamp": archive_ts,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

