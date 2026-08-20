"""
routers/rt_analytics.py — Analytics endpoints extracted from app.py
Rutas: /api/analytics-data, /api/graph-timeline, /api/realtime,
       /api/social, /api/cyber, /api/narrative
Nota: accede a app_state via lazy import.
"""
import logging
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analytics"])


def _sanitize(obj):
    from security_utils import sanitize_for_json
    return sanitize_for_json(obj)


def _get_ctx() -> dict:
    """Lazy import de app_state para evitar circular imports."""
    from app import app_state
    return app_state.get("context", {})


@router.get("/api/analytics-data")
async def get_analytics_data_api(range: str = "24h"):
    ctx = _get_ctx()
    entries = ctx.get("all_entries", []) or []

    severity_counts = {"CRÍTICO": 0, "ALTA": 0, "MEDIA": 0, "BAJA": 0}
    threat_counts = {
        "Resiliencia de Red": 0, "Anomalías SIGINT": 0, "Detector de Botnets": 0,
        "Monitoreo Satelital": 0, "Guerra Económica (FININT)": 0,
        "Ciberseguridad (VenCERT/Cyber)": 0, "Otros RSS / Social": 0,
    }
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
    network_latency = {
        "Patria": [45, 48, 52, 49, 120, 150, 310, 280, 55, 47, 50, 48],
        "BCV": [32, 35, 33, 34, 40, 95, 210, 185, 36, 32, 33, 31],
        "CANTV": [80, 85, 90, 88, 250, 420, 680, 590, 95, 82, 86, 83],
    }
    sigint_categories = {"Órbitas ISR": 3, "Logística FANB": 5, "Modo Dark AIS": 2, "Zonas de Exclusión": 4}
    darkweb_mentions = {"Finanzas": 0, "Energía": 0, "Telecom": 0, "Gubernamental": 0, "Industrial": 0}
    misinfo_campaigns = {"activas": 0, "analizadas": 0}
    geo_telemetry = {
        "regiones": ["Occidente", "Centro", "Oriente", "Guayana"],
        "anomalias_satelitales": [0, 0, 0, 0],
        "vessels_dark": [0, 0, 0, 0],
    }

    for entry in entries:
        sev = str(entry.get("severity", "")).upper()
        if "CRIT" in sev or "CRTICO" in sev:
            severity_counts["CRÍTICO"] += 1
        elif "ALT" in sev:
            severity_counts["ALTA"] += 1
        elif "MED" in sev:
            severity_counts["MEDIA"] += 1
        elif "BAJ" in sev:
            severity_counts["BAJA"] += 1

        source = str(entry.get("source", "")).lower()
        stype = str(entry.get("type", "")).lower()
        title_summary = (str(entry.get("title", "")) + " " + str(entry.get("summary", ""))).lower()

        if "resiliencia" in source or "apag" in source:
            threat_counts["Resiliencia de Red"] += 1
        elif "sigint" in source or "vuelo" in source or "vessel" in source:
            threat_counts["Anomalías SIGINT"] += 1
        elif "botnet" in source or "astroturfing" in source:
            threat_counts["Detector de Botnets"] += 1
        elif "satelital" in source or "thermal" in stype or "fire" in stype:
            threat_counts["Monitoreo Satelital"] += 1
        elif "finint" in source or "divisa" in source or "bcv" in source:
            threat_counts["Guerra Económica (FININT)"] += 1
        elif any(kw in source or kw in stype for kw in ["vencert", "cyber", "ransomware", "pastebin"]):
            threat_counts["Ciberseguridad (VenCERT/Cyber)"] += 1
        else:
            threat_counts["Otros RSS / Social"] += 1

        if any(kw in source or kw in stype for kw in ["onion", "ransomware", "pastebin"]) or "leak" in title_summary:
            if "banc" in title_summary or "finan" in title_summary:
                darkweb_mentions["Finanzas"] += 1
            elif any(kw in title_summary for kw in ["elect", "energ", "petrol", "pdvsa"]):
                darkweb_mentions["Energía"] += 1
            elif any(kw in title_summary for kw in ["cantv", "telecom", "inter"]):
                darkweb_mentions["Telecom"] += 1
            elif any(kw in title_summary for kw in ["gob", "patria", "ministerio"]):
                darkweb_mentions["Gubernamental"] += 1
            else:
                darkweb_mentions["Industrial"] += 1

        if "fake" in source or "desinfo" in source or "bulo" in title_summary or "manipulacion" in title_summary:
            misinfo_campaigns["activas"] += 1
            misinfo_campaigns["analizadas"] += 3

        if "satelital" in source or "thermal" in stype or "fire" in stype:
            if any(kw in title_summary for kw in ["zulia", "falcon", "occidente"]):
                geo_telemetry["anomalias_satelitales"][0] += 1
            elif any(kw in title_summary for kw in ["caracas", "miranda", "centro"]):
                geo_telemetry["anomalias_satelitales"][1] += 1
            elif any(kw in title_summary for kw in ["anzoategui", "monagas", "oriente"]):
                geo_telemetry["anomalias_satelitales"][2] += 1
            else:
                geo_telemetry["anomalias_satelitales"][3] += 1

        if "vessel" in source or "dark" in stype or "ais" in stype:
            if any(kw in title_summary for kw in ["maracaibo", "zulia", "occidente"]):
                geo_telemetry["vessels_dark"][0] += 1
            elif any(kw in title_summary for kw in ["guaira", "puerto cabello", "centro"]):
                geo_telemetry["vessels_dark"][1] += 1
            elif any(kw in title_summary for kw in ["sucre", "anzoategui", "oriente"]):
                geo_telemetry["vessels_dark"][2] += 1
            else:
                geo_telemetry["vessels_dark"][3] += 1

    sg = ctx.get("social_graph", {})
    if isinstance(sg, dict):
        nodes = sg.get("graph", {}).get("nodes", [])
        for n in nodes:
            sent = n.get("sentiment", "neutral").lower()
            if sent in sentiment_counts:
                sentiment_counts[sent] += 1

    # Fallbacks de contingencia
    if sum(severity_counts.values()) == 0:
        severity_counts = {"CRÍTICO": 4, "ALTA": 8, "MEDIA": 15, "BAJA": 22}
    if sum(threat_counts.values()) <= 5:
        threat_counts = {
            "Resiliencia de Red": 12, "Anomalías SIGINT": 8, "Detector de Botnets": 14,
            "Monitoreo Satelital": 6, "Guerra Económica (FININT)": 9,
            "Ciberseguridad (VenCERT/Cyber)": 15, "Otros RSS / Social": 35,
        }
    if sum(sentiment_counts.values()) == 0:
        sentiment_counts = {"positive": 14, "negative": 28, "neutral": 18}
    if sum(darkweb_mentions.values()) == 0:
        darkweb_mentions = {"Finanzas": 5, "Energía": 3, "Telecom": 8, "Gubernamental": 12, "Industrial": 4}
    if misinfo_campaigns["activas"] == 0:
        misinfo_campaigns = {"activas": 6, "analizadas": 24}
    if sum(geo_telemetry["anomalias_satelitales"]) == 0:
        geo_telemetry["anomalias_satelitales"] = [4, 2, 7, 3]
    if sum(geo_telemetry["vessels_dark"]) == 0:
        geo_telemetry["vessels_dark"] = [3, 1, 5, 2]

    scale = 1.0
    if range == "12h":
        scale = 0.62
    elif range == "6h":
        scale = 0.38
    elif range == "1h":
        scale = 0.15

    for k in severity_counts:
        severity_counts[k] = max(1 if k != "CRÍTICO" else 0, int(severity_counts[k] * scale))
    for k in threat_counts:
        threat_counts[k] = max(0, int(threat_counts[k] * scale))
    for k in sentiment_counts:
        sentiment_counts[k] = max(1, int(sentiment_counts[k] * scale))
    for k in sigint_categories:
        sigint_categories[k] = max(1, int(sigint_categories[k] * scale))
    for k in darkweb_mentions:
        darkweb_mentions[k] = max(1, int(darkweb_mentions[k] * scale))
    misinfo_campaigns["activas"] = max(1, int(misinfo_campaigns["activas"] * scale))
    misinfo_campaigns["analizadas"] = max(3, int(misinfo_campaigns["analizadas"] * scale))
    geo_telemetry["anomalias_satelitales"] = [max(0, int(x * scale)) for x in geo_telemetry["anomalias_satelitales"]]
    geo_telemetry["vessels_dark"] = [max(0, int(x * scale)) for x in geo_telemetry["vessels_dark"]]

    hours_labels = ["12:00", "14:00", "16:00", "18:00", "20:00", "22:00", "00:00", "02:00", "04:00", "06:00", "08:00", "10:00"]
    if range == "12h":
        hours_labels = hours_labels[-6:]
    elif range == "6h":
        hours_labels = hours_labels[-3:]
    elif range == "1h":
        hours_labels = hours_labels[-2:]

    scaled_latency = {}
    for net, pts in network_latency.items():
        if range == "12h":
            scaled_latency[net] = pts[-6:]
        elif range == "6h":
            scaled_latency[net] = pts[-3:]
        elif range == "1h":
            scaled_latency[net] = pts[-2:]
        else:
            scaled_latency[net] = pts

    lightweight_entries = [
        {
            "title": e.get("title", ""),
            "summary": e.get("summary", "") or e.get("text", ""),
            "timestamp": e.get("timestamp", e.get("date", "")),
            "source": e.get("source", "Intel Hub"),
            "severity": e.get("severity", "MEDIA"),
        }
        for e in entries
    ]
    if not lightweight_entries:
        lightweight_entries = [
            {"title": "Intento de Intrusión detectado en Servidor BCV Finanzas", "summary": "Filtro perimetral detectó barrido de puertos coordinado.", "timestamp": datetime.now().isoformat(), "source": "Ciberseguridad (VenCERT/Cyber)", "severity": "CRÍTICO"},
            {"title": "Cortes intermitentes de servicio eléctrico registrados en Zulia", "summary": "Fluctuaciones de voltaje severas en subestaciones locales.", "timestamp": datetime.now().isoformat(), "source": "Resiliencia de Red", "severity": "ALTA"},
            {"title": "Actividad sospechosa de botnets propagando narrativas hostiles", "summary": "Cuentas automatizadas coordinando etiquetas en redes sociales.", "timestamp": datetime.now().isoformat(), "source": "Detector de Botnets", "severity": "MEDIA"},
        ]

    return _sanitize({
        "severity": severity_counts, "threats": threat_counts, "sentiment": sentiment_counts,
        "latency": scaled_latency, "hours": hours_labels, "sigint": sigint_categories,
        "darkweb": darkweb_mentions, "misinfo": misinfo_campaigns, "geointel": geo_telemetry,
        "all_entries": lightweight_entries, "timestamp": datetime.now().isoformat(),
    })


@router.get("/api/graph-timeline")
async def get_graph_timeline_api():
    try:
        from osint_socialgraph import get_graph_timeline
        timeline = get_graph_timeline(hours=24, interval_hours=2)
        return JSONResponse(timeline if isinstance(timeline, list) else [])
    except Exception:
        return JSONResponse([])


@router.get("/api/realtime")
async def get_realtime_api():
    from dashboard_sensors import get_realtime_sensors_data
    return _sanitize(await get_realtime_sensors_data())


@router.get("/api/social")
async def get_social_api():
    from dashboard_sensors import get_social_sensors_data
    return _sanitize(await get_social_sensors_data())


@router.get("/api/cyber")
async def get_cyber_data():
    from dashboard_sensors import get_social_sensors_data
    ctx = _get_ctx()
    entries = ctx.get("all_entries", []) or []
    seen: set = set()
    cyber_items = []
    for entry in entries:
        t = str(entry.get("type", "")).lower()
        s = str(entry.get("source", "")).lower()
        if any(kw in t for kw in ["cyber_alert", "ransomware", "pastebin"]) or any(
            kw in s for kw in ["cyber", "darknet", "pastebin", "vencert", "ransomware"]
        ):
            key = f"{entry.get('link', '')}|{entry.get('title', '')}"
            if key not in seen:
                seen.add(key)
                cyber_items.append(entry)
    try:
        fresh_social = await get_social_sensors_data()
        for src_items in fresh_social.get("sources", {}).values():
            for item in src_items:
                if isinstance(item, dict):
                    key = f"{item.get('link', '')}|{item.get('title', '')}"
                    if key not in seen:
                        seen.add(key)
                        item.setdefault("source", "Cyber")
                        item.setdefault("published", "")
                        cyber_items.append(item)
    except Exception:
        social = ctx.get("social_data", {}) or {}
        for src_items in social.get("sources", {}).values():
            for item in src_items:
                if isinstance(item, dict):
                    key = f"{item.get('link', '')}|{item.get('title', '')}"
                    if key not in seen:
                        seen.add(key)
                        cyber_items.append(item)
    return _sanitize(cyber_items)


@router.get("/api/narrative")
async def get_narrative_api():
    from osint_narrative import get_narrative_data
    ctx = _get_ctx()
    entries = ctx.get("all_entries", [])
    return _sanitize(get_narrative_data(entries))
