"""
incidents_manager.py - Gestor de Incidentes Tácticos y Eventos Críticos para COBALTO HUB
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

CUSTOM_INCIDENTS_PATH = Path("data/custom_incidents.json")


def load_custom_incidents() -> List[Dict[str, Any]]:
    if CUSTOM_INCIDENTS_PATH.exists():
        try:
            with open(CUSTOM_INCIDENTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[INCIDENTS] Error cargando incidentes personalizados: {e}")
    return []


def save_custom_incidents(incidents: List[Dict[str, Any]]) -> bool:
    try:
        CUSTOM_INCIDENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CUSTOM_INCIDENTS_PATH, "w", encoding="utf-8") as f:
            json.dump(incidents, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"[INCIDENTS] Error guardando incidentes personalizados: {e}")
        return False


def add_custom_incident(
    title: str,
    theater: str,
    category: str,
    severity: str,
    summary: str,
    latitude: float = 0.0,
    longitude: float = 0.0,
    source: str = "Operador COBALTO",
) -> Dict[str, Any]:
    incidents = load_custom_incidents()
    inc_id = f"inc_{int(time.time())}_{len(incidents)+1}"
    new_inc = {
        "id": inc_id,
        "title": title.strip(),
        "theater": theater.upper(),
        "category": category.upper(),
        "severity": severity.upper(),
        "status": "OPEN",
        "latitude": float(latitude) if latitude else 0.0,
        "longitude": float(longitude) if longitude else 0.0,
        "summary": summary.strip(),
        "source": source,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    incidents.insert(0, new_inc)
    save_custom_incidents(incidents)
    return new_inc


def update_incident_status(incident_id: str, new_status: str) -> bool:
    incidents = load_custom_incidents()
    found = False
    for inc in incidents:
        if inc.get("id") == incident_id:
            inc["status"] = new_status.upper()
            inc["updated_at"] = datetime.utcnow().isoformat() + "Z"
            found = True
            break
    if found:
        save_custom_incidents(incidents)
    return found


def delete_custom_incident(incident_id: str) -> bool:
    incidents = load_custom_incidents()
    initial_len = len(incidents)
    incidents = [i for i in incidents if i.get("id") != incident_id]
    if len(incidents) < initial_len:
        save_custom_incidents(incidents)
        return True
    return False


def extract_incidents_from_historical() -> List[Dict[str, Any]]:
    """Extrae incidentes tácticos reales desde el almacén histórico SQLite."""
    incidents = []
    try:
        from historical_store import query_range
        res = query_range(limit=250)
        entries = res.get("entries", [])

        tactical_kws = {
            "SECURITY": ["detenido", "detención", "incautación", "homicidio", "violencia", "enfrentamiento", "asalto", "secuestro", "droga", "cocaína", "capturado", "fuerzas"],
            "MILITARY": ["militar", "fuerzas armadas", "fanb", "despliegue", "guardia nacional", "ejército", "patrullaje", "operación militar", "defensa"],
            "INFRASTRUCTURE": ["apagón", "eléctrico", "guri", "refinería", "pdvsa", "supermetanol", "telecomunicaciones", "bgp", "vial", "deslizamiento", "bombeo"],
            "CYBER": ["ransomware", "ciberataque", "cve-", "ddos", "exploit", "darknet", "malware", "phishing", "leak", "vencert"],
            "CIB": ["astroturfing", "bot-storm", "campaña coordinada", "desinformación", "troll", "botnet"],
            "PROTEST": ["protesta", "manifestación", "huelga", "paro", "concentración", "marcha", "disturbio", "exigencia"],
            "WEATHER": ["lluvia", "inundación", "sismo", "terremoto", "derrumbamiento", "contingencia"]
        }

        seen_keys = set()
        for e in entries:
            title = e.get("title", "")
            summary = e.get("summary", "")
            combo = (title + " " + summary).lower()

            matched_cat = None
            for cat, kws in tactical_kws.items():
                if any(kw in combo for kw in kws):
                    matched_cat = cat
                    break

            if not matched_cat and e.get("severity") not in ["HIGH", "CRITICAL", "ALTA"]:
                continue

            matched_cat = matched_cat or "SECURITY"

            key = f"{title[:40]}|{e.get('source','')}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

            theater = "GLOBAL"
            if any(k in combo for k in ["venezuela", "caracas", "zulia", "maracaibo", "táchira", "apure", "bolívar", "valencia", "barquisimeto"]):
                theater = "VEN"
            elif any(k in combo for k in ["colombia", "bogotá", "cúcuta", "arauca", "norte de santander", "medellín"]):
                theater = "COL"
            if any(k in combo for k in ["franja", "fronter", "puente internacional", "san antonio", "el amparo"]):
                theater = "FRONTERA"

            sev = e.get("severity") or "HIGH"
            if sev not in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                sev = "HIGH" if matched_cat in ["MILITARY", "CYBER", "CIB"] else "MEDIUM"

            inc_id = f"hist_{e.get('entry_id') or abs(hash(title))}"

            incidents.append({
                "id": inc_id,
                "title": title,
                "theater": theater,
                "category": matched_cat,
                "severity": sev,
                "status": "OPEN",
                "latitude": e.get("lat") or e.get("latitude") or 0.0,
                "longitude": e.get("lng") or e.get("longitude") or 0.0,
                "summary": summary[:300] if summary else "Evento de inteligencia registrado por sensores OSINT.",
                "source": e.get("source") or "Almacén OSINT",
                "timestamp": e.get("published") or e.get("ingested_at") or datetime.utcnow().isoformat() + "Z",
                "created_at": e.get("ingested_at") or datetime.utcnow().isoformat() + "Z",
            })
    except Exception as err:
        logger.debug(f"[INCIDENTS] Error leyendo desde almacén histórico: {err}")
    return incidents


def get_all_incidents() -> List[Dict[str, Any]]:
    # 1. Custom operator incidents
    all_inc = load_custom_incidents()
    existing_ids = {i["id"] for i in all_inc}

    # 2. Ingest auto-detected incidents from real historical OSINT database
    hist_incidents = extract_incidents_from_historical()
    for inc in hist_incidents:
        if inc["id"] not in existing_ids:
            existing_ids.add(inc["id"])
            all_inc.append(inc)

    # 3. Ingest auto-detected incidents from events_tracker (earthquakes, weather alerts, etc.)
    try:
        from events_tracker import get_all_events_data
        ev_data = get_all_events_data()

        # Security & Protests
        auto_items = (ev_data.get("security_incidents", []) or []) + (ev_data.get("protests", []) or [])
        for item in auto_items:
            inc_id = str(item.get("id") or f"auto_{abs(hash(item.get('title', '')))}")
            if inc_id in existing_ids:
                continue
            existing_ids.add(inc_id)

            lat = float(item.get("latitude") or item.get("lat") or 0.0)
            lng = float(item.get("longitude") or item.get("lng") or 0.0)

            theater = "GLOBAL"
            if lat != 0 and lng != 0:
                if 0.5 <= lat <= 13.0 and -73.5 <= lng <= -59.8:
                    theater = "VEN"
                elif -4.5 <= lat <= 13.0 and -79.0 <= lng <= -66.8:
                    theater = "COL"
                elif 6.5 <= lat <= 12.0 and -73.5 <= lng <= -70.0:
                    theater = "FRONTERA"

            all_inc.append({
                "id": inc_id,
                "title": item.get("title", "Incidente de Seguridad"),
                "theater": theater,
                "category": "SECURITY" if item.get("type") == "security" else "PROTEST",
                "severity": item.get("severity", "HIGH"),
                "status": "OPEN",
                "latitude": lat,
                "longitude": lng,
                "summary": item.get("summary", ""),
                "source": item.get("source", "Monitor OSINT"),
                "timestamp": item.get("published") or datetime.utcnow().isoformat() + "Z",
                "created_at": datetime.utcnow().isoformat() + "Z",
            })
    except Exception as e:
        logger.debug(f"[INCIDENTS] Error procesando eventos automáticos: {e}")

    return all_inc

