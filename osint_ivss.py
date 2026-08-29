"""
osint_ivss.py — Extractor de Inteligencia IVSS (Instituto Venezolano de los Seguros Sociales).

Institutional public-OSINT: official press releases, pension payment schedules,
health alerts and official services catalogue published by the IVSS.

Deliberate scope: this module collects ONLY public, institution-level information.
It performs NO profiling of private individuals — the public IVSS portal does not
expose per-citizen account records, and this module never fabricates them.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

IVSS_BASE_URL = "http://www.ivss.gob.ve"
IVSS_NOTICIAS_URL = "http://www.ivss.gob.ve/noticias"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) COBALTO/16.1 OSINT-Intel"

# ── Circuit Breaker State ──
_ivss_cb_lock = threading.Lock()
_ivss_cb = {"disabled_until": 0}
_IVSS_CB_RECOVERY = 600  # 10 minutes

# Public-institution alert categories (pension/salud/movilidad/tramites)
MOVILITY_KW = ["fronter", "paso", "movilidad", "migraci", "movimiento migratorio"]
PENSION_KW = ["pensi", "pago", "bono", "cesta", "jubilado", "cobro"]
SALUD_KW = ["salud", "medicamento", "hospital", "clínica", "clinica", "diálisis", "dialisis", "oncolog", "quirúrg", "quirurg", "vacuna"]
TRAMITES_KW = ["tramite", "trámite", "cita", "registro", "inscripci", "solicitud", "empleador", "patrono"]

# Keywords that flag high-urgency public comms
SEVERITY_KW = ["pago", "pensi", "bono", "urgente", "alerta", "nuevo", "cambio", "ampliaci"]


def _circuit_open() -> bool:
    with _ivss_cb_lock:
        return time.time() < _ivss_cb["disabled_until"]


def _open_circuit():
    with _ivss_cb_lock:
        _ivss_cb["disabled_until"] = time.time() + _IVSS_CB_RECOVERY


def fetch_ivss_noticias() -> List[Dict[str, Any]]:
    """Extrae anuncios oficiales, fechas de pago de pensiones y alertas de salud del IVSS."""
    results: List[Dict[str, Any]] = []
    if _circuit_open():
        return results

    try:
        resp = requests.get(
            IVSS_NOTICIAS_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
            verify=False,
        )
        if resp.status_code != 200:
            _open_circuit()
            return results

        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # News carousel: #banner_noticia > .banner_noticia > div[title] (each a noticia)
        seen_links: set = set()
        for block in soup.select("#banner_noticia .banner_noticia > div"):
            title = block.get("title") or ""
            spans = block.find_all("span")
            title = title or (spans[0].get_text(strip=True) if spans else "")
            link = ""
            a = block.find("a", href=True)
            if a:
                link = a["href"]
                if link.startswith("//"):
                    link = "http:" + link
                elif link.startswith("/"):
                    link = f"{IVSS_BASE_URL}{link}"
                elif not link.lower().startswith("http"):
                    link = f"{IVSS_BASE_URL}/{link}"
            if link in seen_links or not title or len(title) < 10:
                continue
            seen_links.add(link)

            text_body = block.get_text(" ", strip=True)
            published = _extract_date(text_body) or ""

            summary = _fetch_news_summary(link) if link else ""
            if not summary:
                summary = text_body[:250]

            results.append(_build_item(title, link, published, summary))

    except Exception as e:
        logger.warning("[IVSS] Error consultando portal de noticias: %s", e)
        _open_circuit()

    return results


def _extract_date(text: str) -> str:
    """Try to pull a publication date like '05 de marzo de 2021' from body text."""
    m = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})\b", text, re.IGNORECASE)
    if m:
        try:
            month_map = {
                "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
                "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
                "noviembre": 11, "diciembre": 12,
            }
            month = month_map.get(m.group(2).lower())
            if month:
                return f"{int(m.group(1)):02d}-{month:02d}-{m.group(3)}"
        except Exception:
            pass
    return ""


def _fetch_news_summary(url: str) -> str:
    """Fetch the body snippet of an IVSS news article."""
    if not url or url == IVSS_BASE_URL:
        return ""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=12, verify=False)
        if resp.status_code != 200:
            return ""
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        container = soup.find("div", class_="pag_contenido") or soup.find("article")
        text = container.get_text(" ", strip=True) if container else soup.get_text(" ", strip=True)
        return re.sub(r"\s+", " ", text)[:400]
    except Exception as e:
        logger.debug("[IVSS] summary fetch error %s: %s", url, e)
        return ""


def _build_item(title: str, link: str, published: str, summary: str) -> Dict[str, Any]:
    ec = _classify(title + " " + summary)
    severity = "ALTA" if any(k in (title + " " + summary).lower() for k in SEVERITY_KW) else ("INFORMATIVA" if ec == "institucional" else "ALERTA")
    return {
        "title": f"[OFICIAL] 🇻🇪 IVSS: {title}",
        "summary": summary or "Anuncio institucional emitido por el IVSS Venezuela.",
        "link": link,
        "published": published or datetime.now().isoformat(),
        "source": "🇻🇪 IVSS Oficial",
        "type": "gov_announcement",
        "severity": severity,
        "categoria": ec,
        "country": "Venezuela",
    }


def _classify(text: str) -> str:
    """Tag a public comm as pension/salud/tramites/movilidad or institucional."""
    low = text.lower()
    if any(k in low for k in PENSION_KW):
        return "pensiones_pagos"
    if any(k in low for k in SALUD_KW):
        return "salud"
    if any(k in low for k in MOVILITY_KW):
        return "movilidad"
    if any(k in low for k in TRAMITES_KW):
        return "tramites_servicios"
    return "institucional"


def validate_cedula(cedula: str) -> Dict[str, Any]:
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


def ivss_lookup(cedula: str | None = None, scope: str = "institucional") -> Dict[str, Any]:
    """
    IVSS institutional OSINT lookup.

    Collects only PUBLIC institution-level information: official press releases,
    pension/salud/tramites alerts and the official services catalogue.

    NOTE: The public IVSS portal does not expose per-citizen account records, and
    this module never fabricates personal data. Any cédula parameter is answered
    with structural/format validation only, never a per-person record.
    """
    noticias = fetch_ivss_noticias()
    pensiones = [n for n in noticias if n.get("categoria") == "pensiones_pagos"]
    salud = [n for n in noticias if n.get("categoria") == "salud"]
    tramites = [n for n in noticias if n.get("categoria") == "tramites_servicios"]
    movilidad = [n for n in noticias if n.get("categoria") == "movilidad"]
    otras = [n for n in noticias if n.get("categoria") in ("institucional",)]

    result: Dict[str, Any] = {
        "status": "CONSULTADO" if noticias else ("DEGRADADO" if _circuit_open() else "SIN_DATOS"),
        "institucion": "Instituto Venezolano de los Seguros Sociales (IVSS)",
        "pais": "Venezuela",
        "fuente": "🇻🇪 Portal Oficial IVSS",
        "alcance": "OSINT institucional público — sin perfilamiento de personas naturales",
        "comunicados": noticias,
        "pensiones_y_pagos": pensiones,
        "alertas_salud": salud,
        "tramites_y_servicios": tramites,
        "movilidad": movilidad,
        "comunicados_institucionales": otras,
        "timestamp": datetime.now().isoformat(),
    }

    if scope == "alertas":
        result = {
            "alertas": {
                "pensiones_y_pagos": pensiones,
                "salud": salud,
                "movilidad": movilidad,
            },
            "total": len(pensiones) + len(salud) + len(movilidad),
            "timestamp": datetime.now().isoformat(),
        }
    elif scope == "lleno":
        result["servicios_oficiales"] = [
            {"nombre": "Sistema de Gestión y Autoliquidación de Empresas", "descripcion": "Plataforma SICESAUT para empleadores (autoliquidación de aportes)."},
            {"nombre": "Registro de Solicitud de Empleo", "descripcion": "Registro e inscripción institucional de empleadores."},
            {"nombre": "Beneficio Médico Integral", "descripcion": "Atención y cobertura médica institucional a asegurados."},
            {"nombre": "Tipos de Pensiones", "descripcion": "Regímenes de pensiones (vejez, invalidez, sobrevivientes)."},
            {"nombre": "Continuación Facultativa", "descripcion": "Continuación voluntaria de la cotización."},
        ]

    # Cédula parameter: structural validation only, never per-person data.
    if cedula:
        result["documento_consultado"] = {
            "validacion_formato": validate_cedula(cedula),
            "nota": "El portal público IVSS no expone expedientes individuales. Solo validación estructural de formato; no se consulta ni expone información personal.",
        }

    return result


def get_ivss_data() -> Dict[str, Any]:
    """Retorna las novedades y datos procesados del IVSS para el pipeline del dashboard."""
    items = fetch_ivss_noticias()
    return {
        "timestamp": datetime.now().isoformat(),
        "sources": {"🇻🇪 IVSS Oficial": items},
        "count": len(items),
    }


if __name__ == "__main__":
    print("=== TEST EXTRACTOR IVSS VENEZUELA ===")
    data = get_ivss_data()
    print(f"Noticias detectadas: {data['count']}")
    for n in data["sources"].get("🇻🇪 IVSS Oficial", []):
        print(f"- [{n['severity']}][{n.get('categoria','')}] {n['title']}")
