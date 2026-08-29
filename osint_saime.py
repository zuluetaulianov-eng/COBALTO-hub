"""
osint_saime.py — SAIME (Venezuela) Institutional OSINT Engine.
Public-institution intelligence: official press releases, public mobility/border
alerts, official services & procedures catalogue.

Deliberate scope: this module collects ONLY public, institution-level information
published by the SAIME (noticias, comunicados, alertas de movilidad, servicios y
trámites oficiales). It performs NO profiling of private individuals' identity data.
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
_saime_cb_lock = threading.Lock()
_saime_failures = 0
_SAIME_CB_THRESHOLD = 4
_SAIME_CB_RECOVERY = 600  # 10 minutes
_saime_disabled_until = 0

SAIME_BASE = "https://www.saime.gob.ve"
SAIME_FEED = f"{SAIME_BASE}/feed/"
SAIME_NEWS = f"{SAIME_BASE}/index.php/noticias"
SAIME_REST_POSTS = f"{SAIME_BASE}/wp-json/wp/v2/posts"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"

# Keywords that mark mobility / border movement alerts (public institutional comms)
MOBILITY_KEYWORDS = [
    "fronter", "movilidad", "frontera", "pasaporte", "prórroga", "prorroga",
    "habilitación", "habilitacion", "migración", "migracion", "extranjer",
    "paso fronterizo", "puesto de control", "aeropuerto", "paso colombia",
    "paso brasil", "regularización", "regularizacion",
]


def is_saime_available() -> bool:
    global _saime_failures, _saime_disabled_until
    with _saime_cb_lock:
        if time.time() < _saime_disabled_until:
            return False
        return True


def report_saime_failure():
    global _saime_failures, _saime_disabled_until
    with _saime_cb_lock:
        _saime_failures += 1
        if _saime_failures >= _SAIME_CB_THRESHOLD:
            _saime_disabled_until = time.time() + _SAIME_CB_RECOVERY
            logger.warning(f"[SAIME CB] Circuito abierto ({_saime_failures} fallos). Reintentando en {_SAIME_CB_RECOVERY}s.")


def report_saime_success():
    global _saime_failures, _saime_disabled_until
    with _saime_cb_lock:
        _saime_failures = 0
        _saime_disabled_until = 0


def _get_text(url: str, timeout: int = 20) -> str | None:
    """Fetch text content with SSL verification disabled (gov SSL quirks) + UA spoof."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, verify=False)
        if resp.status_code == 200:
            return resp.text
        logger.debug(f"[SAIME] HTTP {resp.status_code} for {url}")
        return None
    except Exception as e:
        logger.debug(f"[SAIME] fetch error {url}: {e}")
        return None


def _parse_feed(xml_text: str, limit: int = 20) -> list[dict]:
    """Parse the SAIME WordPress RSS feed into structured public-press-release items."""
    items: list[dict] = []
    try:
        soup = BeautifulSoup(xml_text, "xml")
        for item in soup.find_all("item")[:limit]:
            title = item.find("title")
            link = item.find("link")
            pubdate = item.find("pubDate")
            desc = item.find("description")
            content = item.find("content:encoded") or item.find("description")
            category = item.find("category")

            text = ""
            if content:
                text = BeautifulSoup(content.get_text(separator=" "), "html.parser").get_text(" ", strip=True)
            elif desc:
                text = BeautifulSoup(desc.get_text(separator=" "), "html.parser").get_text(" ", strip=True)

            items.append({
                "title": (title.get_text(strip=True) if title else ""),
                "link": (link.get_text(strip=True) if link else ""),
                "published": (pubdate.get_text(strip=True) if pubdate else ""),
                "category": (category.get_text(strip=True) if category else "Noticias"),
                "summary": text[:500],
            })
    except Exception as e:
        logger.warning(f"[SAIME FEED] parse error: {e}")
    return items


def _parse_news_page(html_text: str, limit: int = 20) -> list[dict]:
    """Parse the official SAIME Noticias listing page for public press releases."""
    items: list[dict] = []
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        # Articles rendered in Elementor posts; match by headings + date text
        for h in soup.find_all(["h2", "h3", "h4"])[:limit * 3]:
            title = h.get_text(strip=True)
            if not title or len(title) < 8:
                continue
            # Look for nearby date
            date_str = ""
            parent = h.find_parent("article") or h.find_parent("div")
            if parent:
                date_el = parent.find("time")
                if date_el:
                    date_str = date_el.get("datetime", date_el.get_text(strip=True))
            items.append({
                "title": title,
                "link": "",
                "published": date_str,
                "category": "Noticias",
                "summary": "",
            })
            if len(items) >= limit:
                break
    except Exception as e:
        logger.warning(f"[SAIME NEWS] parse error: {e}")
    return items


def _classify_mobility(item: dict) -> str:
    """Tag public comms as mobility/border related or general institutional.

    Classification is based on the title alone to avoid generic agency boilerplate
    (e.g. 'migración', 'extranjería' in the about/perfil text) over-tagging items.
    """
    haystack = item.get("title", "").lower()
    hits = [kw for kw in MOBILITY_KEYWORDS if kw in haystack]
    return "movilidad_fronteriza" if hits else "institucional"


# ── Public institutional lookup (no individual profiling) ──
async def saime_lookup(cedula: str | None = None, scope: str = "institucional") -> dict:
    """
    SAIME institutional OSINT lookup.

    Collects only PUBLIC institution-level information:
      - official press releases / comunicados
      - public mobility & border movement alerts
      - official services & procedures catalogue

    NOTE: This endpoint deliberately does NOT perform identity profiling of private
    individuals (no consultation of citizens' personal records). Requests for
    individual records are answered with an institutional response only.
    """
    if not is_saime_available():
        return {
            "status": "degraded",
            "fuente": "🇻🇪 SAIME (Circuit Breaker Activo)",
            "error": "Portal SAIME temporalmente inaccesible.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    loop = asyncio_loop()
    executor = ThreadPoolExecutor(max_workers=3)

    def _fetch_institutional():
        comms = []
        # 1. RSS feed (structured)
        feed_xml = _get_text(SAIME_FEED)
        if feed_xml:
            comms.extend(_parse_feed(feed_xml, limit=15))
        # 2. News listing page fallback
        news_html = _get_text(SAIME_NEWS)
        if news_html:
            page_items = _parse_news_page(news_html, limit=10)
            feed_titles = {c.get("title") for c in comms}
            for it in page_items:
                if it["title"] not in feed_titles:
                    comms.append(it)

        for c in comms:
            c["mobility_tag"] = _classify_mobility(c)
            if not c["link"]:
                c["link"] = SAIME_BASE

        return comms

    try:
        comms = await loop.run_in_executor(executor, _fetch_institutional)
        report_saime_success()
    except Exception as e:
        logger.warning(f"[SAIME] lookup error: {e}")
        report_saime_failure()
        comms = []

    mobility = [c for c in comms if c["mobility_tag"] == "movilidad_fronteriza"]
    institutional = [c for c in comms if c["mobility_tag"] == "institucional"]

    result = {
        "status": "CONSULTADO",
        "institucion": "Servicio Administrativo de Identificación, Migración y Extranjería (SAIME)",
        "pais": "Venezuela",
        "fuente": "🇻🇪 Portal Oficial SAIME (https://www.saime.gob.ve)",
        "alcance": "OSINT institucional público — sin perfilamiento de personas naturales",
        "comunicados": comms,
        "alertas_movilidad_fronteriza": mobility,
        "comunicados_institucionales": institutional,
        "servicios_oficiales": [
            {"nombre": "Identificación", "descripcion": "Emisión, prórroga y rectificación de cédulas de identidad."},
            {"nombre": "Migración", "descripcion": "Movimientos migratorios nacionales y entradas/salidas."},
            {"nombre": "Extranjería", "descripcion": "Residencia y regularización de extranjeros."},
            {"nombre": "Pasaporte", "descripcion": "Emisión, renovación y habilitación de pasaportes."},
            {"nombre": "Verificación y Registro", "descripcion": "Solicitudes y seguimiento de trámites institucionales."},
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Cédula parameter: only perform structural/format validation (institution-level),
    # never a lookup of a person's private record.
    if cedula:
        result["documento_consultado"] = {
            "validacion_formato": _validate_cedula(cedula),
            "nota": "Solo validación estructural. Los datos personales de los ciudadanos no se consultan ni se exponen.",
        }

    if scope == "lleno":
        result["portal"] = {"url_base": SAIME_BASE, "noticias": SAIME_NEWS, "feed": SAIME_FEED, "api_rest": SAIME_REST_POSTS}
    elif scope == "alertas":
        result = {"alertas_movilidad_fronteriza": mobility, "total": len(mobility), "timestamp": datetime.now(timezone.utc).isoformat()}

    return result


async def saime_alerts() -> dict:
    """Fast endpoint: only public mobility/border movement alerts."""
    data = await saime_lookup(scope="alertas")
    return data


def _validate_cedula(cedula: str) -> dict:
    """Structural/format validation of a Venezuelan cédula — returns NO personal data."""
    if not cedula:
        return {"valida": False, "motivo": "Documento vacío"}
    cleaned = re.sub(r"[^A-Za-z0-9]", "", cedula).upper()
    letter = cleaned[:1] if cleaned else ""
    digits = cleaned[1:] if cleaned and cleaned[0] in "VE" else cleaned
    if letter not in ("V", "E"):
        return {"valida": False, "motivo": "Nacionalidad debe ser V (venezolano) o E (extranjero)"}
    if not digits.isdigit() or not (5 <= len(digits) <= 8):
        return {"valida": False, "motivo": "Rango de dígitos inválido (5-8)"}
    return {"valida": True, "nacionalidad": letter, "formato_largo": len(digits), "solo_validacion_estructural": True}


def asyncio_loop():
    """Return the current running event loop or a fresh one."""
    try:
        import asyncio
        return asyncio.get_event_loop()
    except Exception:
        import asyncio
        return asyncio.new_event_loop()


def get_saime_data() -> dict:
    """Dashboard Sensor integration (public institutional comms)."""
    comms = []
    feed_xml = _get_text(SAIME_FEED)
    if feed_xml:
        comms = _parse_feed(feed_xml, limit=10)
    mobility = [c for c in comms if _classify_mobility(c) == "movilidad_fronteriza"]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "🇻🇪 SAIME Comunicados": mobility if mobility else comms
        },
        "count": len(mobility) if mobility else len(comms),
    }
