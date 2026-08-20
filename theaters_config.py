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
    based on domain, text keywords, and source name.
    """
    tags = set()
    domain_lower = domain.lower()
    text_lower = text.lower()
    source_lower = source.lower()

    theaters = get_active_theaters()
    for code, t_data in theaters.items():
        if code == "GLOBAL":
            continue

        # Check domain & source
        for d in t_data.get("domains", []):
            d_clean = d.lower().split(".")[0]
            if d.lower() in domain_lower or d_clean in source_lower or d.lower() in source_lower:
                tags.add(code)
                break

        # Check keywords
        if code not in tags:
            for kw in t_data.get("keywords", []):
                if kw in text_lower or kw in source_lower:
                    tags.add(code)
                    break

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
