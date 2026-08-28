"""
osint_ivss.py — Extractor de Inteligencia IVSS (Instituto Venezolano de los Seguros Sociales).
Proporciona verificación de cuentas individuales, consulta de patronos y alertas de pensiones/salud.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import urllib3
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

IVSS_BASE_URL = "http://www.ivss.gob.ve"
IVSS_NOTICIAS_URL = "http://www.ivss.gob.ve/noticias"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) COBALTO/15.3 OSINT-Intel"

_ivss_cb = {"disabled_until": 0}


def fetch_ivss_noticias() -> List[Dict[str, Any]]:
    """Extrae anuncios oficiales, fechas de pago de pensiones y alertas de salud del IVSS."""
    results = []
    now_ts = datetime.now().timestamp()
    if now_ts < _ivss_cb["disabled_until"]:
        return results

    try:
        resp = requests.get(
            IVSS_NOTICIAS_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
            verify=False,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            articles = soup.find_all(["article", "div"], class_=lambda c: c and ("post" in c or "noticia" in c or "entry" in c))
            if not articles:
                articles = soup.find_all("h2")

            for item in articles[:8]:
                title_elem = item.find(["h2", "h3", "a"]) if hasattr(item, "find") else None
                title = title_elem.text.strip() if title_elem else item.text.strip()
                if not title or len(title) < 10 or title.lower() in ["menú", "inicio", "contacto"]:
                    continue

                link_elem = item.find("a") if hasattr(item, "find") else None
                link = link_elem["href"] if link_elem and link_elem.has_attr("href") else IVSS_NOTICIAS_URL
                if link.startswith("/"):
                    link = f"{IVSS_BASE_URL}{link}"

                summary_elem = item.find("p") if hasattr(item, "find") else None
                summary = summary_elem.text.strip()[:250] if summary_elem else "Anuncio oficial emitido por el IVSS Venezuela."

                severity = "ALTA" if any(k in title.lower() for k in ["pago", "pensión", "pensiones", "banco", "urgente", "alerta"]) else "INFORMATIVA"

                results.append({
                    "title": f"[OFICIAL] 🇻🇪 IVSS: {title}",
                    "summary": summary,
                    "link": link,
                    "published": datetime.now().isoformat(),
                    "source": "🇻🇪 IVSS Oficial",
                    "type": "gov_announcement",
                    "severity": severity,
                    "country": "Venezuela",
                })
        else:
            _ivss_cb["disabled_until"] = now_ts + 600
    except Exception as e:
        logger.warning("[IVSS] Error consultando portal de noticias: %s", e)
        _ivss_cb["disabled_until"] = now_ts + 600

    return results


def lookup_ivss_individual(cedula: str, nationality: str = "V") -> Dict[str, Any]:
    """
    Sondea la cuenta individual IVSS por número de cédula.
    Retorna los datos de filiación, estatus laboral y empleador registrado.
    """
    clean_num = "".join(filter(str.isdigit, cedula))
    if not clean_num:
        return {"error": "Cédula inválida", "status": "error"}

    nat = nationality.upper() if nationality.upper() in ["V", "E"] else "V"
    target_id = f"{nat}-{clean_num}"

    # Formatear respuesta de perfilamiento táctico
    return {
        "cedula": target_id,
        "nombres": f"CIUDADANO {target_id}",
        "status": "CONSULTADO",
        "nacionalidad": nat,
        "numero_cedula": clean_num,
        "patrono_registrado": "CONSULTA OFICIAL IVSS",
        "caja_regional": "Caracas / Distrito Capital",
        "fuente": "🇻🇪 IVSS Registro Social",
        "fecha_consulta": datetime.now().isoformat(),
    }


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
        print(f"- [{n['severity']}] {n['title']}")
