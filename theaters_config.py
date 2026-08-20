"""
theaters_config.py — COBALTO HUB Multi-Theater Operational Registry
Manages regional surveillance vectors, auto-tagging rules, geospatial focal points,
and domain/target user mapping across multiple countries.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

THEATERS_DIR = Path(__file__).parent / "data" / "theaters"

DEFAULT_THEATERS: Dict[str, Dict[str, Any]] = {
    "COL": {
        "code": "COL",
        "name": "Colombia",
        "flag": "🇨🇴",
        "enabled": True,
        "description": "Monitoreo del conflicto armado, seguridad regional y transición política en Colombia",
        "geo_center": [6.5, -70.0],
        "default_zoom": 5,
        "domains": [
            "vanguardia.com", "elpais.com.co", "lafm.com.co", "bluradio.com",
            "cambiocolombia.com", "verdadabierta.com", "pares.com.co", "france24.com",
            "eltiempo.com", "elespectador.com", "semana.com", "noticias.caracoltv.com",
            "noticiasrcn.com", "elheraldo.co", "elcolombiano.com", "lasillavacia.com"
        ],
        "keywords": [
            "colombia", "bogotá", "bogota", "medellín", "medellin", "cali", "cauca",
            "catatumbo", "arauca", "tumaco", "putumayo", "chocó", "eln", "emc",
            "marquetalia", "clan del golfo", "gaitanistas", "petro", "caño limón",
            "paz total", "gaula", "ffmm colombia"
        ],
        "target_users": ["ArielAvilaAnaliza", "LeonVaLenciaA", "FIP_Col", "Indepaz", "DanielMejiaL", "lasillavacia", "DefensoriaCol"],
        "seismic_geofence": {"lat": 4.711, "lon": -74.0721, "max_distance_km": 600}
    },
    "VEN": {
        "code": "VEN",
        "name": "Venezuela",
        "flag": "🇻🇪",
        "enabled": True,
        "description": "Vigilancia de seguridad, infraestructura, cibernética y dinámicas político-militares en Venezuela",
        "geo_center": [7.5, -66.5],
        "default_zoom": 6,
        "domains": [
            "elpitazo.net", "runrun.es", "lapatilla.com", "efectococuyo.com",
            "talcualdigital.com", "eldiario.com", "vencert.gob.ve", "mpprijp.gob.ve"
        ],
        "keywords": [
            "venezuela", "caracas", "maracaibo", "valencia", "barquisimeto", "zulia",
            "tachira", "fanb", "padrino lópez", "maduro", "diosdado", "cantv", "sebin"
        ],
        "target_users": ["PresidencialVen", "PrensaFANB", "REDI_Capital", "DouglasRicoVzla"],
        "seismic_geofence": {"lat": 10.4806, "lon": -66.9036, "max_distance_km": 400}
    },
    "GLOBAL": {
        "code": "GLOBAL",
        "name": "Global / Internacional",
        "flag": "🌐",
        "enabled": True,
        "description": "Monitoreo geoestratégico global y noticias de seguridad internacional",
        "geo_center": [7.0, -68.0],
        "default_zoom": 4,
        "domains": ["reuters.com", "bbc.com", "apnews.com", "dw.com", "cnn.com", "insightcrime.org"],
        "keywords": [],
        "target_users": ["InSightCrime", "UN_Spokesperson"],
        "seismic_geofence": {"lat": 8.0, "lon": -68.0, "max_distance_km": 1500}
    }
}


def ensure_theaters_dir():
    """Ensure the theaters directory exists and default profiles are written."""
    THEATERS_DIR.mkdir(parents=True, exist_ok=True)
    for code, data in DEFAULT_THEATERS.items():
        file_path = THEATERS_DIR / f"{code.lower()}.json"
        if not file_path.exists():
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"[THEATERS] Could not write default theater {code}: {e}")


def load_all_theaters() -> Dict[str, Dict[str, Any]]:
    """Load all theater JSON files from data/theaters/."""
    ensure_theaters_dir()
    theaters = {}
    for p in THEATERS_DIR.glob("*.json"):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
                code = data.get("code", p.stem.upper()).upper()
                theaters[code] = data
        except Exception as e:
            logger.error(f"[THEATERS] Failed loading {p}: {e}")

    # Fallback to default if empty
    if not theaters:
        theaters = DEFAULT_THEATERS.copy()
    return theaters


def get_active_theaters() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of active/enabled theaters."""
    all_t = load_all_theaters()
    return {k: v for k, v in all_t.items() if v.get("enabled", True)}


def get_theater(code: str) -> Dict[str, Any]:
    """Get theater config by country code."""
    theaters = load_all_theaters()
    return theaters.get(code.upper(), {})


def detect_country_tags(text: str = "", domain: str = "", source: str = "") -> List[str]:
    """
    Detect country codes associated with a piece of intelligence
    based on exact source mapping, TLDs, domain names, and text keywords.
    """
    tags = set()
    domain_lower = domain.lower()
    text_lower = text.lower()
    source_lower = source.lower()

    # 1. Mapeo directo por nombre exacto de la fuente (sin ambigüedades)
    VEN_SOURCES = {
        "venevisión", "venevisión oficial", "noticiero venevisión", "el nacional",
        "el estímulo", "el estimulo", "el diario", "runrun.es", "runrunes",
        "efecto cocuyo", "caracas chronicles", "evtv miami", "evtv", "el pitazo",
        "el pitazo venezuela", "crónica uno", "cronica uno", "últimas noticias",
        "ultimas noticias", "2001 online", "el impulso", "el carabobeño",
        "el carabobeno", "la patilla", "la patilla canal", "alnavío", "alnavio",
        "descifrado", "telesur", "vtv canal 8", "vtv", "vencert alertas",
        "vencert boletines", "vencert general", "banca y negocios",
        "finanzas digital", "dolartoday", "albertorodnews (venezuela)", "albertorodnews",
        "anonymousvenezuela", "cyberhuntersven", "teamhdp", "presidencialven",
        "padrinovladimir"
    }

    COL_SOURCES = {
        "noticias caracol", "el tiempo", "el tiempo colombia", "la silla vacía",
        "la silla vacia", "el espectador", "revista semana", "semana",
        "noticias rcn", "rcn", "blu radio colombia", "blu radio", "pulzo",
        "vanguardia", "el país (colombia)", "el colombiano", "el heraldo",
        "cambio colombia", "verdad abierta", "fundación pares", "pares",
        "caracol radio", "caracol radio oficial", "w radio", "w radio colombia",
        "radio nacional de colombia", "cuestión pública", "cuestion publica",
        "vorágine", "voragine", "la opinión", "la opinion", "la opinión cúcuta",
        "periódico del meta", "periodicodelmeta", "la nación", "la nacion",
        "rcn radio", "infopresidencia", "fuerzasmilcol", "policiacolombia", "mindefensa",
        "ejército nacional", "ejercito_col", "armada de colombia", "armadacolombia",
        "fuerza aeroespacial", "fuerzaaereacol", "fiscalía general", "fiscaliacol",
        "defensoriacol", "unpcolombia", "petrogustavo", "franciamarquezm", "laurisarabia",
        "arielavilaanaliza", "leonvalenciaa", "fip_col", "indepaz", "danielmejial",
        "mariafdacabal", "palomavalencial", "vickydavilah", "alvarouribevel", "ficogutierrez"
    }

    for s_name in VEN_SOURCES:
        if s_name in source_lower:
            tags.add("VEN")
            break

    for s_name in COL_SOURCES:
        if s_name in source_lower:
            tags.add("COL")
            break

    # 2. Análisis por Dominios / TLDs explícitos
    if ".com.ve" in domain_lower or ".gob.ve" in domain_lower or ".ve/" in domain_lower or domain_lower.endswith(".ve"):
        tags.add("VEN")
    if ".com.co" in domain_lower or ".gov.co" in domain_lower or ".edu.co" in domain_lower:
        tags.add("COL")

    # 3. Análisis por Dominios registrados en teatros activos
    theaters = get_active_theaters()
    for code, t_data in theaters.items():
        if code == "GLOBAL":
            continue

        for d in t_data.get("domains", []):
            d_clean = d.lower()
            if d_clean in domain_lower or (len(d_clean) > 4 and d_clean in source_lower):
                tags.add(code)
                break

    # 4. Análisis por términos clave en el contenido o título de la noticia
    VEN_KEYWORDS = [
        "venezuela", "venezolano", "venezolana", "caracas", "maracaibo", "valencia",
        "barquisimeto", "zulia", "táchira", "tachira", "fanb", "padrino lópez",
        "padrino lopez", "maduro", "diosdado", "cantv", "sebin", "ceofanb",
        "miraflores", "pdvsa", "esequibo", "anzoátegui", "monagas", "bolívar",
        "aragua", "lara", "falcón", "margarita", "carabobo"
    ]

    COL_KEYWORDS = [
        "colombia", "colombiano", "colombiana", "bogotá", "bogota", "medellín",
        "medellin", "cali", "cauca", "catatumbo", "arauca", "tumaco", "putumayo",
        "chocó", "choco", "eln", "emc", "marquetalia", "clan del golfo",
        "gaitanistas", "petro", "caño limón", "paz total", "gaula",
        "ffmm colombia", "cúcuta", "cucuta", "casa de nariño", "mindefensa"
    ]

    if "VEN" not in tags:
        if any(kw in text_lower for kw in VEN_KEYWORDS):
            tags.add("VEN")

    if "COL" not in tags:
        if any(kw in text_lower for kw in COL_KEYWORDS):
            tags.add("COL")

    if not tags:
        tags.add("GLOBAL")

    return list(tags)


def save_theater(theater_data: Dict[str, Any]) -> bool:
    """Save or update a theater profile JSON."""
    ensure_theaters_dir()
    code = theater_data.get("code", "").upper()
    if not code:
        return False

    file_path = THEATERS_DIR / f"{code.lower()}.json"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(theater_data, f, indent=2, ensure_ascii=False)
        logger.info(f"[THEATERS] Saved theater profile: {code}")
        return True
    except Exception as e:
        logger.error(f"[THEATERS] Error saving theater {code}: {e}")
        return False
