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


def get_all_incidents() -> List[Dict[str, Any]]:
    # 1. Custom operator incidents
    all_inc = load_custom_incidents()

    # 2. Ingest auto-detected incidents from events_tracker (fast attempt)
    try:
        from events_tracker import get_all_events_data
        ev_data = get_all_events_data()

        # Security & Protests
        auto_items = (ev_data.get("security_incidents", []) or []) + (ev_data.get("protests", []) or [])
        for item in auto_items:
            inc_id = str(item.get("id") or f"auto_{abs(hash(item.get('title', '')))}")
            if any(i["id"] == inc_id for i in all_inc):
                continue

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

    # Fallback default operational incidents if list is empty
    if not all_inc:
        all_inc = [
            {
                "id": "inc_col_01",
                "title": "🇨🇴 Despliegue de Unidad de Respuesta Rápida en Norte de Santander",
                "theater": "COL",
                "category": "MILITARY",
                "severity": "CRITICAL",
                "status": "OPEN",
                "latitude": 7.8939,
                "longitude": -72.5078,
                "summary": "Movilización táctica preventivo-defensiva tras detección de movimientos inusuales de vectores no identificados en franja fronteriza.",
                "source": "Comando de Operaciones Conjuntas",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "created_at": datetime.utcnow().isoformat() + "Z",
            },
            {
                "id": "inc_ven_01",
                "title": "🇻🇪 Interrupción de Señal de Telecomunicaciones en San Cristóbal",
                "theater": "VEN",
                "category": "INFRASTRUCTURE",
                "severity": "HIGH",
                "status": "INVESTIGATING",
                "latitude": 7.7669,
                "longitude": -72.2250,
                "summary": "Caída del 45% en el tráfico BGP regional. Anomalía electromagnética o falla estructural en repedidor central.",
                "source": "Telemetría OSIRIS / SIGINT",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "created_at": datetime.utcnow().isoformat() + "Z",
            },
            {
                "id": "inc_cib_01",
                "title": "⚡ Campaña de Astroturfing Coordinada en Redes Sociales",
                "theater": "GLOBAL",
                "category": "CIB",
                "severity": "HIGH",
                "status": "CONTAINED",
                "latitude": 10.4806,
                "longitude": -66.9036,
                "summary": "Inyección masiva de 1,400 bots difundiendo narrativa contrainteligencia desestabilizadora.",
                "source": "Sensor Bot-Storm COBALTO",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "created_at": datetime.utcnow().isoformat() + "Z",
            },
        ]

    return all_inc
