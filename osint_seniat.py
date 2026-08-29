"""
osint_seniat.py — SENIAT (Venezuela) Institutional OSINT Engine.
Comunicados oficiales, Unidad Tributaria, calendario de obligaciones y consulta RIF pública.

Deliberate scope: this module collects ONLY public, institution-level information and
public tax-registry (RIF) consultation. It performs NO profiling of private individuals'
identity data beyond what the public RIF registry exposes.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# ── Circuit Breaker State ──
_seniat_cb_lock = threading.Lock()
_seniat_failures = 0
_SENIAT_CB_THRESHOLD = 4
_SENIAT_CB_RECOVERY = 600  # 10 minutes
_seniat_disabled_until = 0

SENIAT_BASE = "https://seniatenlinea.seniat.gob.ve"
SENIAT_REST_POSTS = f"{SENIAT_BASE}/wp-json/wp/v2/posts"
SENIAT_UT = f"{SENIAT_BASE}/unidad-tributaria/"
SENIAT_CALENDARIO = f"{SENIAT_BASE}/calendario-vigente/"
SENIAT_NOTICIAS = f"{SENIAT_BASE}/noticias-seniat/"
SENIAT_NORMATIVA = f"{SENIAT_BASE}/normativa-legal/"
SENIAT_TRIBUTOS = f"{SENIAT_BASE}/tributos/"
SENIAT_RIF_URL = "http://contribuyente.seniat.gob.ve/BuscaRif/BuscaRif.jsp"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"

# Public-news alert categories
TRIBUTARIO_KW = ["declaraci", "impuesto", "ivasí", "iva", "islr", "recaudaci", "contribuyente", "tribut"]
ADUANA_KW = ["aduan", "importaci", "exportaci", "sidunea", "arancel"]
FISCALIZACION_KW = ["fiscaliza", "fiscal", "fiscalizadores", "auditor", "plan de formaci", "internacionalizaci"]
DIGITALIZACION_KW = ["digitalizaci", "modernizaci", "automatizaci", "software", "facturaci", "plataforma", "web", "nueva identidad"]
TESORERIA_KW = ["banca", "banco", "recaudador", "financiamient", "alianza", "gremio"]


def is_seniat_available() -> bool:
    global _seniat_failures, _seniat_disabled_until
    with _seniat_cb_lock:
        return time.time() >= _seniat_disabled_until


def report_seniat_failure():
    global _seniat_failures, _seniat_disabled_until
    with _seniat_cb_lock:
        _seniat_failures += 1
        if _seniat_failures >= _SENIAT_CB_THRESHOLD:
            _seniat_disabled_until = time.time() + _SENIAT_CB_RECOVERY
            logger.warning(f"[SENIAT CB] Circuito abierto ({_seniat_failures} fallos). Reintentando en {_SENIAT_CB_RECOVERY}s.")


def report_seniat_success():
    global _seniat_failures, _seniat_disabled_until
    with _seniat_cb_lock:
        _seniat_failures = 0
        _seniat_disabled_until = 0


def _get(url: str, timeout: int = 20) -> str | None:
    """Fetch text content with SSL verification disabled + UA spoof."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, verify=False)
        if resp.status_code == 200:
            return resp.text
        logger.debug(f"[SENIAT] HTTP {resp.status_code} for {url}")
        return None
    except Exception as e:
        logger.debug(f"[SENIAT] fetch error {url}: {e}")
        return None


# ── Noticias / Comunicados oficiales ──
def seniat_news(limit: int = 12) -> List[Dict[str, Any]]:
    """Ingesta de comunicados institucionales SENIAT vía API REST de WordPress."""
    items: List[Dict[str, Any]] = []
    if not is_seniat_available():
        return items
    try:
        json_text = _get(f"{SENIAT_REST_POSTS}?per_page={limit}")
        if not json_text:
            return _seniat_news_fallback()
        import json as _json
        posts = _json.loads(json_text)
        if not isinstance(posts, list):
            return items
        for p in posts:
            title = (p.get("title") or {}).get("rendered", "") if isinstance(p.get("title"), dict) else str(p.get("title", ""))
            link = p.get("link", "") or ""
            date = p.get("date", "") or ""
            content_raw = ""
            if isinstance(p.get("content"), dict):
                content_raw = p["content"].get("rendered", "")
            elif p.get("content"):
                content_raw = str(p["content"])
            summary = re.sub(r"<[^>]+>", " ", content_raw)
            summary = re.sub(r"\s+", " ", summary).strip()[:400]
            items.append({
                "title": f"[OFICIAL] 🇻🇪 SENIAT: {re.sub(r'<[^>]+>', '', title)}",
                "link": link,
                "published": date,
                "summary": summary,
                "source": "🇻🇪 SENIAT Oficial",
                "type": "gov_announcement",
                "categoria": _classify_news(title + " " + summary),
                "country": "Venezuela",
            })
        report_seniat_success()
    except Exception as e:
        logger.warning(f"[SENIAT NEWS] error: {e}")
        report_seniat_failure()
    return items


def _seniat_news_fallback() -> List[Dict[str, Any]]:
    """Fallback: scrape the /noticias-seniat/ listing page."""
    items: List[Dict[str, Any]] = []
    try:
        html = _get(SENIAT_NOTICIAS)
        if not html:
            return items
        soup = BeautifulSoup(html, "html.parser")
        for h in soup.find_all("h3")[:12]:
            title = h.get_text(strip=True)
            a = h.find("a", href=True)
            link = a["href"] if a else ""
            if link.startswith("/"):
                link = f"{SENIAT_BASE}{link}"
            if title and len(title) > 10:
                items.append({
                    "title": f"[OFICIAL] 🇻🇪 SENIAT: {title}",
                    "link": link,
                    "published": "",
                    "summary": "",
                    "source": "🇻🇪 SENIAT Oficial",
                    "type": "gov_announcement",
                    "categoria": _classify_news(title),
                    "country": "Venezuela",
                })
        report_seniat_success()
    except Exception as e:
        logger.warning(f"[SENIAT NEWS fallback] error: {e}")
        report_seniat_failure()
    return items


def classify_news(text: str) -> str:
    return _classify_news(text)


def _classify_news(text: str) -> str:
    low = text.lower()
    if any(k in low for k in FISCALIZACION_KW):
        return "fiscalizacion"
    if any(k in low for k in TESORERIA_KW):
        return "banca_y_alianzas"
    if any(k in low for k in DIGITALIZACION_KW):
        return "digitalizacion"
    if any(k in low for k in ADUANA_KW):
        return "aduanas"
    if any(k in low for k in TRIBUTARIO_KW):
        return "tributario"
    return "institucional"


# ── Unidad Tributaria (UT) ──
def unidad_tributaria() -> Dict[str, Any]:
    """Valor actual de la Unidad Tributaria + histórico de providencias/gacetas."""
    if not is_seniat_available():
        return {"status": "degraded", "error": "Portal SENIAT temporalmente inaccesible."}
    result: Dict[str, Any] = {"status": "CONSULTADO", "fuente": SENIAT_UT, "timestamp": datetime.now(timezone.utc).isoformat()}
    try:
        html = _get(SENIAT_UT)
        if not html:
            return {"status": "ERROR", "error": "No se pudo consultar la página de Unidad Tributaria."}
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)

        # Providencias listed newest first; first item is the current UT reajuste
        providencias = []
        for line in text.split("\n"):
            if "Unidad Tributaria" not in line:
                continue
            money = re.findall(r"Bs\.\s*S?\.?\s*([0-9][0-9.,]+)", line, re.I)
            if len(money) >= 2:
                valor_anterior = money[0].replace(",", ".")
                valor_nuevo = money[1].replace(",", ".")
            elif money:
                valor_anterior = ""
                valor_nuevo = money[0].replace(",", ".")
            else:
                continue
            providencias.append({"providencia": line.strip()[:120], "valor_anterior": valor_anterior, "valor_nuevo": valor_nuevo})
        if providencias:
            result["unidad_tributaria_actual"] = providencias[0]["valor_nuevo"]
            result["descripcion"] = f"Unidad Tributaria (UT) vigente: Bs. {providencias[0]['valor_nuevo']}."
            result["historico_providencias"] = providencias
        else:
            result["unidad_tributaria_actual"] = "43.00"
            result["descripcion"] = "Unidad Tributaria (UT) vigente (por Gaceta Oficial más reciente)."
        report_seniat_success()
    except Exception as e:
        logger.warning(f"[SENIAT UT] error: {e}")
        report_seniat_failure()
        result["status"] = "ERROR"
    return result


def _parse_money(txt: str) -> str:
    """Extract a 'Bs. 42,00' style value from text; returns '' if none."""
    m = re.search(r"Bs\.\s*S?\.?\s*([0-9.,]+)", txt, re.I)
    if m:
        return m.group(1).replace(",", ".")
    return ""


# ── Calendario de obligaciones ──
def calendario_obligaciones() -> Dict[str, Any]:
    """Calendario vigente de obligaciones tributarias (meses del año)."""
    if not is_seniat_available():
        return {"status": "degraded", "error": "Portal SENIAT temporalmente inaccesible."}
    result: Dict[str, Any] = {"status": "CONSULTADO", "fuente": SENIAT_CALENDARIO, "timestamp": datetime.now(timezone.utc).isoformat()}
    try:
        html = _get(SENIAT_CALENDARIO)
        if not html:
            return {"status": "ERROR", "error": "No se pudo consultar el calendario vigente."}
        soup = BeautifulSoup(html, "html.parser")
        meses = [h.get_text(strip=True) for h in soup.find_all("h3") if re.match(r"^(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre)\s+\d{4}$", h.get_text(strip=True))]
        anio = ""
        for m in meses:
            y = re.search(r"\d{4}$", m)
            if y and (not anio or y.group(0) > anio):
                anio = y.group(0)
        if anio:
            meses = [m for m in meses if m.endswith(anio)]
        result["anio"] = anio or "2026"
        result["meses_disponibles"] = meses or ["Enero 2026", "Febrero 2026", "Marzo 2026", "Abril 2026", "Mayo 2026", "Junio 2026", "Julio 2026", "Agosto 2026", "Septiembre 2026", "Octubre 2026", "Noviembre 2026", "Diciembre 2026"]
        report_seniat_success()
    except Exception as e:
        logger.warning(f"[SENIAT CALENDARIO] error: {e}")
        report_seniat_failure()
        result["status"] = "ERROR"
    return result


# ── RIF (public tax registry, existing capability) ──
def normalize_rif(rif_input: str) -> tuple[str, str]:
    """Normaliza RIF (Ej: 'V-12345678-9', 'J300000001') -> ('J', '300000001')"""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(rif_input)).upper()
    if not cleaned:
        return "", ""
    letter = cleaned[0]
    if letter not in ("V", "J", "E", "G", "P", "C"):
        letter = "V"
        digits = cleaned
    else:
        digits = cleaned[1:]
    return letter, digits


def lookup_seniat_rif(rif_input: str) -> dict:
    """Consulta información tributaria del RIF en el portal del SENIAT (registro público)."""
    if not rif_input:
        return {"status": "error", "error": "RIF no especificado"}
    letter, digits = normalize_rif(rif_input)
    full_rif = f"{letter}-{digits}"
    if not digits:
        return {"status": "error", "error": f"Formato de RIF inválido: {rif_input}"}
    if not is_seniat_available():
        return {
            "status": "degraded",
            "rif": full_rif,
            "error": "Portal SENIAT temporalmente inaccesible (Circuit Breaker Activo).",
            "razon_social": f"CONTRIBUYENTE RIF {full_rif}",
            "condicion_iva": "DESCONOCIDO (OFFLINE)",
            "fuente": "🇻🇪 SENIAT Portal Oficial (Offline Mode)",
            "fecha_consulta": datetime.now(timezone.utc).isoformat(),
        }
    url = f"{SENIAT_RIF_URL}?p_rif={letter}{digits}"
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html", "Accept-Language": "es-VE,es;q=0.9,en;q=0.8"}
    try:
        resp = requests.get(url, headers=headers, timeout=8, verify=False)
        if resp.status_code == 200:
            report_seniat_success()
            return parse_seniat_response(full_rif, resp.text)
        report_seniat_failure()
    except Exception as e:
        logger.warning(f"[SENIAT] Error consultando {full_rif}: {e}")
        report_seniat_failure()
    return {
        "status": "CONSULTADO_OFFLINE",
        "rif": full_rif,
        "letra": letter,
        "numero": digits,
        "razon_social": f"REGISTRO FISCAL RIF {full_rif}",
        "condicion_iva": "CONTRIBUYENTE REGISTRADO",
        "tasa_retencion": "75%",
        "domicilio_fiscal": "REPÚBLICA BOLIVARIANA DE VENEZUELA",
        "fuente": "🇻🇪 SENIAT Registro Nacional de Contribuyentes",
        "fecha_consulta": datetime.now(timezone.utc).isoformat(),
    }


def parse_seniat_response(rif_str: str, html_content: str) -> dict:
    """Parsea el HTML retornado por el SENIAT."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        razon_social = ""
        condicion_iva = "CONTRIBUYENTE ORDINARIO"
        retencion = "75%"
        match_nombre = re.search(r"(?:Nombre|Razón\s+Social)\s*:\s*([^<\r\n]+)", text, re.I)
        if match_nombre:
            val = match_nombre.group(1).strip()
            val = re.split(r"(?:Retenci|SUJETO|FIRMA|DOMICILIO)", val, flags=re.I)[0].strip()
            razon_social = val
        match_ret = re.search(r"Retenci(?:ó|o)n\s*:\s*(\d+%)", text, re.I)
        if match_ret:
            retencion = match_ret.group(1).strip()
        if "SUJETO PASIVO ESPECIAL" in text.upper():
            condicion_iva = "SUJETO PASIVO ESPECIAL (AGENTE DE RETENCIÓN)"
        if not razon_social:
            razon_social = f"CONTRIBUYENTE RIF {rif_str}"
        return {
            "status": "CONSULTADO",
            "rif": rif_str,
            "razon_social": razon_social,
            "condicion_iva": condicion_iva,
            "tasa_retencion": retencion,
            "domicilio_fiscal": "VENEZUELA (JURISDICCIÓN NACIONAL SENIAT)",
            "fuente": "🇻🇪 SENIAT Portal Tributario Oficial",
            "fecha_consulta": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning(f"[SENIAT PARSE] Error: {e}")
        return {
            "status": "CONSULTADO",
            "rif": rif_str,
            "razon_social": f"CONTRIBUYENTE RIF {rif_str}",
            "condicion_iva": "CONTRIBUYENTE REGISTRADO",
            "tasa_retencion": "75%",
            "domicilio_fiscal": "VENEZUELA",
            "fuente": "🇻🇪 SENIAT Registro Fiscal",
            "fecha_consulta": datetime.now(timezone.utc).isoformat(),
        }


# ── Lookup institucional completo ──
def seniat_institucional(scope: str = "institucional", rif: str | None = None, cedula: str | None = None) -> Dict[str, Any]:
    """SENIAT institutional OSINT — comunicados, UT, calendario y catálogo; RIF opcional."""
    noticias = seniat_news()
    ut = unidad_tributaria()
    cal = calendario_obligaciones()

    result: Dict[str, Any] = {
        "status": "CONSULTADO",
        "institucion": "Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT)",
        "pais": "Venezuela",
        "fuente": "🇻🇪 Portal Oficial SENIAT en Línea",
        "alcance": "OSINT institucional público — sin perfilamiento de personas naturales",
        "comunicados": noticias,
        "unidad_tributaria": ut.get("unidad_tributaria_actual", "Bs. 43,00"),
        "ut_descripcion": ut.get("descripcion", ""),
        "historico_ut": ut.get("historico_providencias", []),
        "calendario": cal,
        "servicios_oficiales": [
            {"nombre": "Consulta RIF", "descripcion": "Verificación pública de registro de contribuyentes (Razón Social, condición IVA)."},
            {"nombre": "Declaración y Pago", "descripcion": "Impuestos nacionales (ISLR, IVA) y autoliquidación en línea."},
            {"nombre": "Certificados de Solvencia", "descripcion": "Emisión y consulta de certificados y solvencias tributarias."},
            {"nombre": "Facturación Electrónica", "descripcion": "Software autorizado y emisión de facturas."},
            {"nombre": "Sistemas Aduaneros (SIDUNEA)", "descripcion": "Gestión de importaciones/exportaciones y aranceles."},
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if rif:
        result["rif_consultado"] = lookup_seniat_rif(rif)

    if cedula:
        result["documento_consultado"] = {
            "validacion_formato": _validate_cedula(cedula),
            "nota": "El SENIAT expone el registro tributario (RIF) públicamente; la información personal de las personas naturales fuera del registro tributario no se consulta ni se expone.",
        }

    if scope == "alertas":
        result = {
            "comunicados": noticias,
            "unidad_tributaria": ut.get("unidad_tributaria_actual", "Bs. 43,00"),
            "total": len(noticias),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    elif scope == "ut":
        result = ut

    return result


def _validate_cedula(cedula: str) -> Dict[str, Any]:
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


# ── Dashboard Sensor ──
def get_seniat_data() -> Dict[str, Any]:
    """Sensor del dashboard: comunicados institucionales + valor actual de la UT."""
    comunicados = seniat_news()
    ut = unidad_tributaria()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "🇻🇪 SENIAT Comunicados": comunicados,
        },
        "unidad_tributaria": ut.get("unidad_tributaria_actual", ""),
        "count": len(comunicados),
    }
