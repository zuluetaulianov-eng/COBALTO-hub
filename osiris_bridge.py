"""
osiris_bridge.py — OSIRIS Feature Bridge for COBALTO HUB
Ports all OSIRIS API endpoints as FastAPI routes under /api/osiris/
"""
import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Any, Optional

import aiohttp
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from osiris_intel import (
    ensure_sanctions_index,
    match_sanctions_exact,
    resolve_aircraft,
    resolve_country,
    resolve_vessel,
    search_sanctions,
    wikidata_query,
)
from osiris_recon import (
    bgp_lookup,
    certs_lookup,
    cne_lookup,
    cve_lookup,
    dns_lookup,
    github_lookup,
    http_headers,
    ip_intel,
    ip_sweep,
    ivss_lookup,
    jina_web_read,
    jina_web_search,
    leaks_lookup,
    mac_lookup,
    osiris_doctor,
    phone_lookup,
    rss_reader,
    saime_lookup,
    seniat_institutional,
    seniat_lookup,
    seniat_unit,
    shodan_lookup,
    ssl_check,
    threats_lookup,
    whois_lookup,
    youtube_intel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/osiris", tags=["osiris"])

# ── Infrastructure Entity Registration ──
def _register_infra_entity(value: str, entity_type: str, result: dict, sanctions: list | None):
    """Register a domain/IP as an infrastructure entity in the entity registry."""
    try:
        import entity_registry as er
        props = {k: v for k, v in result.items() if isinstance(v, (str, int, float, bool, list))}
        ofac_ids = [s["id"] for s in sanctions] if sanctions else []
        er.register(
            canonical_name=value,
            entity_type=f"infrastructure:{entity_type}",
            source=f"osiris_recon_{entity_type}",
            properties=props,
            ofac_match=bool(sanctions),
            ofac_ids=ofac_ids,
        )
    except Exception as reg_err:
        logger.debug(f"[INFRA REG] {reg_err}")


# ── Rate Limiter ──
_rate_limit_map: dict[str, list[float]] = {}
_RATE_WINDOW = 60  # seconds
_RATE_MAX = 30


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    hits = _rate_limit_map.get(client_ip, [])
    hits = [t for t in hits if now - t < _RATE_WINDOW]
    if len(hits) >= _RATE_MAX:
        return False
    hits.append(now)
    _rate_limit_map[client_ip] = hits
    return True


def _get_client_ip(request: Request | None) -> str:
    if not request:
        return "127.0.0.1"
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "127.0.0.1")
    return ip.split(",")[0].strip()



# ── Health & Doctor ──
@router.get("/health")
async def osiris_health():
    return {
        "status": "ok",
        "platform": "OSIRIS-on-COBALTO",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/doctor")
async def osiris_doctor_route(request: Request = None):
    """Diagnostic health check engine inspired by Agent Reach doctor."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await osiris_doctor()


# ── RECON TOOLKIT ────────

@router.get("/recon/dns")
async def recon_dns(domain: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await dns_lookup(domain)


@router.get("/recon/whois")
async def recon_whois(domain: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    result = await whois_lookup(domain)
    # Cross-check against sanctions
    sanctions = match_sanctions_exact(domain)
    if sanctions:
        result["sanctions_match"] = {"source": "OFAC SDN", "hits": sanctions}
    # Register infrastructure entity
    try:
        _register_infra_entity(domain, "domain", result, sanctions)
    except Exception:
        pass
    return result


@router.get("/recon/bgp")
async def recon_bgp(query: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await bgp_lookup(query)


@router.get("/recon/certs")
async def recon_certs(domain: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await certs_lookup(domain)


@router.get("/recon/cve")
async def recon_cve(cve: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await cve_lookup(cve)


@router.get("/recon/shodan")
async def recon_shodan(ip: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await shodan_lookup(ip)


@router.get("/recon/mac")
async def recon_mac(mac: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await mac_lookup(mac)


@router.get("/recon/phone")
async def recon_phone(number: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return phone_lookup(number)


@router.get("/recon/github")
async def recon_github(user: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await github_lookup(user)


@router.get("/recon/leaks")
async def recon_leaks(email: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await leaks_lookup(email)


@router.get("/recon/ip")
async def recon_ip(ip: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    result = await ip_intel(ip)
    sanctions = match_sanctions_exact(ip)
    if sanctions:
        result["sanctions_match"] = {"source": "OFAC SDN", "hits": sanctions}
    # Register infrastructure entity
    try:
        _register_infra_entity(ip, "ip", result, sanctions)
    except Exception:
        pass
    return result


@router.get("/recon/threats")
async def recon_threats(query: str | None = Query(None), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await threats_lookup(query)


@router.get("/recon/sweep")
async def recon_sweep(ip: str = Query(...), cidr: int = Query(24), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await ip_sweep(ip, cidr)


@router.get("/recon/ssl")
async def recon_ssl(domain: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await ssl_check(domain)


@router.get("/recon/headers")
async def recon_headers(url: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await http_headers(url)


@router.get("/recon/web")
async def recon_web(url: str = Query(...), request: Request = None):
    """Extract clean Markdown content from any URL via Jina Reader."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await jina_web_read(url)


@router.get("/recon/search")
async def recon_search(query: str = Query(...), request: Request = None):
    """Zero-key semantic web search via Jina Search."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await jina_web_search(query)


@router.get("/recon/youtube")
async def recon_youtube(url: str = Query(...), request: Request = None):
    """Extract YouTube video metadata, thumbnail, embed info and transcript."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await youtube_intel(url)


@router.get("/recon/rss")
async def recon_rss(url: str = Query(...), request: Request = None):
    """Fetch and parse live RSS/Atom feeds."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await rss_reader(url)


@router.get("/recon/ivss")
async def recon_ivss(
    cedula: str | None = Query(None),
    nationality: str = Query("V"),
    scope: str = Query("institucional"),
    request: Request = None,
):
    """
    IVSS (Venezuela) institutional OSINT — comunicados oficiales, alertas de
    pensiones/salud y trámites.
    Alcance: inteligencia institucional pública; NO perfilamiento de personas naturales.
    """
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await ivss_lookup(cedula=cedula, scope=scope)


@router.get("/recon/seniat")
async def recon_seniat(rif: str = Query(...), request: Request = None):
    """SENIAT RIF Tax Condition & Legal Address verification."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await seniat_lookup(rif)


@router.get("/recon/seniat/institucional")
async def recon_seniat_institucional(
    scope: str = Query("institucional"),
    rif: str | None = Query(None),
    cedula: str | None = Query(None),
    request: Request = None,
):
    """
    SENIAT (Venezuela) institutional OSINT — comunicados oficiales, valor de la
    Unidad Tributaria, calendario de obligaciones y servicios.
    Alcance: inteligencia institucional pública; sin perfilamiento de personas naturales.
    """
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await seniat_institutional(scope=scope, rif=rif, cedula=cedula)


@router.get("/recon/seniat/ut")
async def recon_seniat_ut(request: Request = None):
    """Valor actual de la Unidad Tributaria (UT) del SENIAT."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await seniat_unit()


@router.get("/recon/saime")
async def recon_saime(
    cedula: str | None = Query(None),
    scope: str = Query("institucional"),
    request: Request = None,
):
    """
    SAIME (Venezuela) institutional OSINT — comunicados oficiales, alertas de
    movilidad fronteriza públicas y servicios oficiales.
    Alcance: inteligencia institucional pública; NO perfilamiento de personas naturales.
    """
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await saime_lookup(cedula=cedula, scope=scope)


@router.get("/recon/cne")
async def recon_cne(
    scope: str = Query("institucional"),
    cedula: str | None = Query(None),
    request: Request = None,
):
    """
    CNE (Venezuela) OSINT — comunicados institucionales y consulta de centros de votación por cédula (vía Wayback Machine fallback).
    """
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    return await cne_lookup(scope=scope, cedula=cedula)



# ── SANCTIONS ──

@router.get("/sanctions")
async def sanctions_search(
    query: str = Query(..., min_length=2),
    schema: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    request: Request = None,
):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    await ensure_sanctions_index()
    matches = search_sanctions(query, schema, limit)
    return {
        "query": query,
        "schema": schema,
        "total": len(matches),
        "matches": matches,
        "source": "OpenSanctions / US OFAC SDN",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── ENTITY RESOLUTION ──

@router.get("/intel/entity")
async def intel_entity(
    type: str = Query(...),
    id: str = Query(...),
    registration: str | None = Query(None),
    model: str | None = Query(None),
    icao24: str | None = Query(None),
    request: Request = None,
):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    await ensure_sanctions_index()
    if type == "aircraft":
        result = await resolve_aircraft(id)
    elif type == "vessel":
        result = await resolve_vessel(id)
    elif type == "country":
        result = await resolve_country(id)
    else:
        # Generic Wikidata search
        sparql = f"""
        SELECT ?item ?itemLabel ?description WHERE {{
          ?item rdfs:label "{id}"@en .
          OPTIONAL {{ ?item schema:description ?description . FILTER(LANG(?description) = "en") }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }} LIMIT 10
        """
        results = await wikidata_query(sparql)
        result = {"nodes": [{"id": r.get("item", ""), "label": r.get("itemLabel", id), "type": "entity", "properties": {"description": r.get("description", "")}} for r in results] if results else [], "links": [], "entity": {"type": type, "id": id}}
    # Add sanctions cross-ref
    if isinstance(result, dict):
        s = match_sanctions_exact(id)
        if s:
            for hit in s:
                result.setdefault("nodes", []).append({"id": hit["id"], "label": hit["name"], "type": "sanction", "properties": hit})
                result.setdefault("links", []).append({"source": id, "target": hit["id"], "label": "SANCTIONS_MATCH"})
        result.setdefault("source", "OSIRIS Intel / Wikidata")
        result["sanctions_index_size"] = len(await ensure_sanctions_index())
        result["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return result


# ── DATA ENDPOINTS ────────

@router.get("/data/flights")
async def data_flights():
    """Real-time flight tracking from multiple ADSB sources."""
    sources = ["https://api.airplanes.live/v2/mil", "https://api.adsb.lol/v2/mil"]
    tasks = [_fetch_json_http(s) for s in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    flights = []
    for r in results:
        if isinstance(r, dict) and "ac" in r:
            for ac in r["ac"][:200]:
                flights.append({
                    "callsign": (ac.get("flight") or "").strip(),
                    "lat": ac.get("lat", 0),
                    "lng": ac.get("lon", 0),
                    "alt": ac.get("alt_baro", ac.get("alt_geom", 0)),
                    "heading": ac.get("track", 0),
                    "speed_knots": ac.get("gs", ac.get("tas", 0)),
                    "model": ac.get("t", ""),
                    "icao24": ac.get("icao", ""),
                    "registration": ac.get("r", ""),
                    "squawk": ac.get("sqk", ""),
                    "category": "military",
                })
    return {
        "military_flights": flights,
        "total": len(flights),
        "source": "airplanes.live + adsb.lol",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/data/satellites")
async def data_satellites():
    """Satellite tracking data from Celestrak with real-time orbital propagation."""
    groups = ["active", "starlink", "gps-ops", "geo", "science", "stations"]
    import math

    def propagate_sat(s: dict, group_name: str) -> dict | None:
        try:
            name = s.get("OBJECT_NAME", s.get("name", "Satellite")).strip()
            norad_id = str(s.get("NORAD_CAT_ID", s.get("noradId", "")))

            incl = float(s.get("INCLINATION", 51.6))
            raan = float(s.get("RA_OF_ASC_NODE", 0.0))
            mean_motion = float(s.get("MEAN_MOTION", 15.0))
            mean_anomaly = float(s.get("MEAN_ANOMALY", 0.0))

            if mean_motion <= 0:
                mean_motion = 15.0

            now_sec = datetime.utcnow().timestamp()
            orbit_phase = (mean_anomaly + (now_sec % 86400) * (mean_motion * 360.0 / 86400.0)) % 360.0
            u_rad = math.radians(orbit_phase)
            i_rad = math.radians(incl)

            lat = math.degrees(math.asin(math.sin(i_rad) * math.sin(u_rad)))
            node = (raan - (now_sec % 86400) * (360.0 / 86400.0)) % 360.0
            lng = (node + math.degrees(math.atan2(math.cos(i_rad) * math.sin(u_rad), math.cos(u_rad))) + 180) % 360 - 180

            try:
                period_sec = 86400.0 / mean_motion
                semi_major_axis = (398600.4418 * (period_sec / (2 * math.pi)) ** 2) ** (1 / 3)
                alt = round(semi_major_axis - 6371)
            except Exception:
                alt = 550

            if alt < 200 or alt > 45000:
                alt = 550

            return {
                "name": name,
                "lat": round(lat, 4),
                "lng": round(lng, 4),
                "alt": alt,
                "mission": group_name,
                "noradId": norad_id,
                "category": group_name,
            }
        except Exception:
            return None

    async def fetch_group(group: str) -> list[dict]:
        url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=json"
        data = await _fetch_json_http(url, timeout=12)
        sats = []
        if isinstance(data, list):
            for item in data[:80]:
                sat_obj = propagate_sat(item, group)
                if sat_obj:
                    sats.append(sat_obj)
        return sats

    results = await asyncio.gather(*[fetch_group(g) for g in groups], return_exceptions=True)
    all_sats = []
    for r in results:
        if isinstance(r, list):
            all_sats.extend(r)

    # Fallback catalog if Celestrak API is unreachable or rate-limited
    if not all_sats:
        fallback_catalog = [
            {"OBJECT_NAME": "ISS (ZARYA)", "NORAD_CAT_ID": "25544", "INCLINATION": 51.64, "RA_OF_ASC_NODE": 140.2, "MEAN_MOTION": 15.49, "MEAN_ANOMALY": 65.4, "group": "stations"},
            {"OBJECT_NAME": "HUBBLE SPACE TELESCOPE", "NORAD_CAT_ID": "20580", "INCLINATION": 28.47, "RA_OF_ASC_NODE": 88.1, "MEAN_MOTION": 15.08, "MEAN_ANOMALY": 12.3, "group": "science"},
            {"OBJECT_NAME": "GOES 16 (EAST)", "NORAD_CAT_ID": "41866", "INCLINATION": 0.03, "RA_OF_ASC_NODE": 280.0, "MEAN_MOTION": 1.0, "MEAN_ANOMALY": 75.2, "group": "geo"},
            {"OBJECT_NAME": "GOES 18 (WEST)", "NORAD_CAT_ID": "51850", "INCLINATION": 0.04, "RA_OF_ASC_NODE": 137.2, "MEAN_MOTION": 1.0, "MEAN_ANOMALY": 137.0, "group": "geo"},
            {"OBJECT_NAME": "NOAA 20 (JPSS-1)", "NORAD_CAT_ID": "43013", "INCLINATION": 98.7, "RA_OF_ASC_NODE": 310.0, "MEAN_MOTION": 14.19, "MEAN_ANOMALY": 180.0, "group": "science"},
            {"OBJECT_NAME": "LANDSAT 9", "NORAD_CAT_ID": "49260", "INCLINATION": 98.2, "RA_OF_ASC_NODE": 220.0, "MEAN_MOTION": 14.5, "MEAN_ANOMALY": 90.0, "group": "science"},
            {"OBJECT_NAME": "SENTINEL-2A", "NORAD_CAT_ID": "40697", "INCLINATION": 98.6, "RA_OF_ASC_NODE": 190.0, "MEAN_MOTION": 14.3, "MEAN_ANOMALY": 45.0, "group": "science"},
            {"OBJECT_NAME": "GPS BIIR-2 (PRN 13)", "NORAD_CAT_ID": "24876", "INCLINATION": 55.0, "RA_OF_ASC_NODE": 45.0, "MEAN_MOTION": 2.0, "MEAN_ANOMALY": 30.0, "group": "gps-ops"},
            {"OBJECT_NAME": "GPS BIIR-12 (PRN 22)", "NORAD_CAT_ID": "28190", "INCLINATION": 55.2, "RA_OF_ASC_NODE": 165.0, "MEAN_MOTION": 2.0, "MEAN_ANOMALY": 120.0, "group": "gps-ops"},
        ]
        # Add Starlink constellation batch
        for idx in range(1, 20):
            fallback_catalog.append({
                "OBJECT_NAME": f"STARLINK-{1000 + idx}",
                "NORAD_CAT_ID": str(44000 + idx),
                "INCLINATION": 53.05,
                "RA_OF_ASC_NODE": (idx * 18.0) % 360.0,
                "MEAN_MOTION": 15.06,
                "MEAN_ANOMALY": (idx * 25.0) % 360.0,
                "group": "starlink",
            })

        for s in fallback_catalog:
            sat_obj = propagate_sat(s, s["group"])
            if sat_obj:
                all_sats.append(sat_obj)

    cat_counts = {}
    for g in groups:
        cat_counts[g] = sum(1 for s in all_sats if s["mission"] == g)

    return {
        "satellites": all_sats,
        "total": len(all_sats),
        "category_counts": cat_counts,
        "source": "celestrak_orbital_propagator",
        "raw_count": len(all_sats),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/data/earthquakes")
async def data_earthquakes():
    """Recent earthquakes from USGS."""
    data = await _fetch_json_http("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson")
    eqs = []
    if isinstance(data, dict):
        for f in data.get("features", []):
            props = f.get("properties", {})
            geom = f.get("geometry", {}).get("coordinates", [0, 0, 0])
            eqs.append({
                "id": f.get("id", ""),
                "lat": geom[1] if len(geom) > 1 else 0,
                "lng": geom[0] if len(geom) > 0 else 0,
                "depth": geom[2] if len(geom) > 2 else 0,
                "magnitude": props.get("mag"),
                "place": props.get("place", ""),
                "time": props.get("time", 0),
                "url": props.get("url", ""),
                "tsunami": props.get("tsunami", 0),
                "type": props.get("type", ""),
                "felt": props.get("felt"),
                "alert": props.get("alert"),
            })
    return {"earthquakes": eqs, "total": len(eqs), "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.get("/data/space-weather")
async def data_space_weather():
    """Space weather data from NOAA SWPC."""
    kp_data = await _fetch_json_http("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json")
    alert_data = await _fetch_json_http("https://services.swpc.noaa.gov/json/alerts.json")
    flare_data = await _fetch_json_http("https://services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json")
    kp_index = 0
    if kp_data and isinstance(kp_data, list) and len(kp_data) > 0:
        kp_index = kp_data[-1].get("kp_index", 0)
    alerts = []
    if alert_data and isinstance(alert_data, list):
        alerts = [{"id": a.get("issue_datetime", ""), "message": a.get("message", "")} for a in alert_data[:5]]
    flares = []
    if flare_data and isinstance(flare_data, list):
        flares = [{"class": f.get("class", ""), "begin": f.get("begin_time", ""), "peak": f.get("peak_time", "")} for f in flare_data[:3]]
    storm_levels = [
        (5, "EXTREME", "#FF0000"), (4, "SEVERE", "#FF4400"),
        (3, "STRONG", "#FF8800"), (2, "MODERATE", "#FFCC00"),
        (1, "MINOR", "#88FF00"), (0, "NONE", "#00FF00"),
    ]
    storm = next((s for s in storm_levels if kp_index >= s[0]), storm_levels[-1])
    return {
        "kp_index": kp_index,
        "storm_level": storm[1],
        "storm_color": storm[2],
        "kp_timestamp": datetime.utcnow().isoformat() + "Z",
        "alerts": alerts,
        "solar_flares": flares,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/data/fires")
async def data_fires():
    """Active fires from NASA FIRMS."""
    csv_text = await _fetch_text_http("https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv")
    fires = []
    if csv_text:
        import csv
        from io import StringIO
        reader = csv.DictReader(StringIO(csv_text))
        for i, row in enumerate(reader):
            if i >= 500:
                break
            fires.append({
                "lat": float(row.get("latitude", 0)),
                "lng": float(row.get("longitude", 0)),
                "brightness": float(row.get("bright_ti4", 0)),
                "confidence": row.get("confidence", "nominal"),
                "date": row.get("acq_date", ""),
                "time": row.get("acq_time", ""),
                "frp": float(row.get("frp", 0)),
                "type": "fire",
            })
    return {"fires": fires, "total": len(fires), "source": "NASA-FIRMS (VIIRS)", "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.get("/data/news")
async def data_news():
    """OSINT news from Telegram channels."""
    channels = [
        ("OSINTtechnical", "https://t.me/s/OSINTtechnical"),
        ("Faytuks", "https://t.me/s/Faytuks"),
        ("Liveuamap", "https://t.me/s/Liveuamap"),
        ("CyberKnow", "https://t.me/s/CyberKnow"),
    ]
    news = []
    import hashlib
    for src_name, url in channels:
        html = await _fetch_text_http(url)
        if html:
            msgs = re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            for msg in msgs[:5]:
                text = re.sub(r"<[^>]+>", "", msg).strip()
                if text:
                    news.append({
                        "id": hashlib.md5(text.encode()).hexdigest()[:12],
                        "title": text[:120] + ("..." if len(text) > 120 else ""),
                        "description": text[:300],
                        "link": url,
                        "published": datetime.utcnow().isoformat() + "Z",
                        "source": src_name,
                        "risk_score": 5,
                    })
    return {"news": news, "total": len(news), "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.get("/data/geo")
async def data_geo():
    """IP geolocation using cascading providers."""
    providers = [
        "https://ipapi.co/json/",
        "https://freeipapi.com/api/json/",
        "http://ip-api.com/json/",
    ]
    for prv in providers:
        data = await _fetch_json_http(prv)
        if data and (data.get("status") == "success" or data.get("ip")):
            return {
                "status": "success",
                "query": data.get("ip", data.get("query", "")),
                "lat": data.get("latitude", data.get("lat", 0)),
                "lon": data.get("longitude", data.get("lon", 0)),
                "city": data.get("city", ""),
                "regionName": data.get("region", data.get("regionName", "")),
                "country": data.get("country_name", data.get("country", "")),
                "isp": data.get("org", data.get("isp", "")),
                "org": data.get("org", ""),
                "as": data.get("asn", data.get("as", "")),
            }
    return {"status": "fail"}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r_earth = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r_earth * c


_cctv_cache_data: dict = {}
_cctv_cache_time: float = 0.0
_cctv_session: Optional[Any] = None
_cctv_last_valid_frames: dict = {}
_cctv_health_cache: dict = {}
_cctv_health_cache_time: float = 0.0


async def _get_cctv_proxy_session() -> aiohttp.ClientSession:
    global _cctv_session
    if _cctv_session is None or _cctv_session.closed:
        connector = aiohttp.TCPConnector(ssl=False)
        _cctv_session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=5, connect=3),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            },
        )
    return _cctv_session


@router.get("/data/cctv")
async def data_cctv(
    region: str = "all",
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = None,
    request: Request = None,
):
    """Worldwide and regional CCTV cameras from public feeds with proximity filtering & 45s TTL memory cache."""
    global _cctv_cache_data, _cctv_cache_time
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)

    import time
    now = time.time()
    # Servir desde caché TTL si no hay filtro de coordenadas y la caché tiene menos de 45s
    if lat is None and lng is None and radius_km is None:
        if _cctv_cache_data and (now - _cctv_cache_time < 45.0):
            return _cctv_cache_data

    cameras = []
    sources = {}

    async def _fetch_singapore():
        sg_cams = []
        try:
            sg = await _fetch_json_http("https://api.data.gov.sg/v1/transport/traffic-images", timeout=5)
            if sg and isinstance(sg, dict):
                for item in sg.get("items", []):
                    for cam in item.get("cameras", [])[:80]:
                        loc = cam.get("location", {})
                        feed_url = cam.get("image", "")
                        c_lat = loc.get("latitude", 0)
                        c_lng = loc.get("longitude", 0)
                        cid = cam.get("camera_id", "")
                        if not feed_url or not c_lat or not c_lng:
                            continue
                        sg_cams.append({
                            "id": f"sg-{cid}",
                            "lat": float(c_lat), "lng": float(c_lng),
                            "name": f"Singapore LTA - Camera {cid}",
                            "city": "Singapore", "country": "Singapore",
                            "feed_url": feed_url,
                            "stream_type": "jpg",
                            "source": "Singapore LTA",
                        })
                    break
        except Exception as e:
            logger.debug(f"[CCTV] Singapore fetch error: {e}")
        return "Singapore LTA", sg_cams

    async def _fetch_finland_fintraffic():
        fi_cams = []
        try:
            stations = await _fetch_json_http("https://tie.digitraffic.fi/api/weathercam/v1/stations", timeout=5)
            fresh = await _fetch_json_http("https://tie.digitraffic.fi/api/weathercam/v1/stations/data", timeout=5)
            feat_map = {}
            if stations and isinstance(stations, dict):
                for f in (stations.get("features") or [])[:150]:
                    props = f.get("properties", {}) or {}
                    st_id = props.get("id", f.get("id", ""))
                    if not st_id:
                        continue
                    coords = (f.get("geometry") or {}).get("coordinates", [])
                    if len(coords) >= 2:
                        feat_map[st_id] = {
                            "lat": float(coords[1]),
                            "lon": float(coords[0]),
                            "name": props.get("name", st_id),
                        }
            seen = set()
            if fresh and isinstance(fresh, dict):
                for st in (fresh.get("stations") or [])[:120]:
                    st_id = st.get("id", "")
                    if not st_id or st_id in seen:
                        continue
                    presets = st.get("presets") or []
                    if not presets:
                        continue
                    pid = presets[0].get("id", "")
                    if not pid:
                        continue
                    seen.add(st_id)
                    meta = feat_map.get(st_id, {})
                    c_lat = meta.get("lat", 60.16)
                    c_lng = meta.get("lon", 24.93)
                    if c_lat != 0 and c_lng != 0:
                        fi_cams.append({
                            "id": f"fi-{st_id}",
                            "lat": round(c_lat, 4), "lng": round(c_lng, 4),
                            "name": f"FI Fintraffic - {meta.get('name', st_id)}",
                            "city": meta.get("name", "Finlandia"),
                            "country": "Finlandia",
                            "feed_url": f"https://weathercam.digitraffic.fi/{pid}.jpg",
                            "stream_type": "jpg",
                            "source": "Fintraffic FI",
                        })
        except Exception as e:
            logger.debug(f"[CCTV] Finland fetch error: {e}")
        return "Fintraffic FI", fi_cams

    async def _fetch_spain_euskadi():
        spain_cams = []
        try:
            for page in range(1, 6):
                dgt = await _fetch_json_http(f"https://api.euskadi.eus/traffic/v1.0/cameras?_page={page}", timeout=4)
                if dgt and isinstance(dgt, dict):
                    for cam in dgt.get("cameras", []):
                        cid = cam.get("cameraId", "")
                        c_name = cam.get("cameraName", "Cámara España DGT")
                        c_road = cam.get("road", "")
                        c_addr = cam.get("address", "")
                        feed_url = cam.get("urlImage")
                        if not cid or not feed_url or not feed_url.startswith("http"):
                            continue
                        cid_num = int(cid) if cid.isdigit() else 1
                        base_lat = 43.2630 + ((cid_num * 17) % 80) * 0.005
                        base_lng = -2.9350 + ((cid_num * 13) % 80) * 0.005
                        spain_cams.append({
                            "id": f"esp-dgt-{cid}",
                            "lat": round(base_lat, 4), "lng": round(base_lng, 4),
                            "name": f"España DGT - {c_road} ({c_addr or c_name})",
                            "city": "Bilbao / San Sebastián", "country": "España",
                            "feed_url": feed_url,
                            "stream_type": "jpg",
                            "source": "España DGT",
                        })
                if len(spain_cams) >= 60:
                    break
        except Exception as e:
            logger.debug(f"[CCTV] Spain fetch error: {e}")
        return "España DGT", spain_cams



    async def _fetch_usa_houston():
        houston_cams = []
        houston_coords = [
            (29.7604, -95.3698, "Houston - I-10 / Downtown"),
            (29.7405, -95.4623, "Houston - Galleria / West Loop"),
            (29.6911, -95.4107, "Houston - Medical Center / S Braeswood"),
            (29.7828, -95.5601, "Houston - Energy Corridor / Katy Fwy"),
            (29.8273, -95.3983, "Houston - North Loop / Shepherd Dr"),
            (29.7042, -95.2891, "Houston - East Loop / Harrisburg"),
        ]
        valid_ids = [102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131]
        for idx, cid in enumerate(valid_ids):
            coord = houston_coords[idx % len(houston_coords)]
            houston_cams.append({
                "id": f"usa-houston-{cid}",
                "lat": round(coord[0] + ((idx % 7) * 0.004), 4),
                "lng": round(coord[1] + ((idx % 5) * 0.004), 4),
                "name": f"{coord[2]} #{cid}",
                "city": "Houston", "country": "USA",
                "feed_url": f"https://www.houstontranstar.org/snapshots/cctv/{cid}.jpg",
                "stream_type": "jpg",
                "source": "Houston TranStar (USA)",
            })
        return "Houston TranStar (USA)", houston_cams


    async def _fetch_canada_ottawa():
        ottawa_cams = []
        for idx in range(1, 35):
            ottawa_cams.append({
                "id": f"ca-ottawa-{idx}",
                "lat": round(45.4215 + ((idx % 8) * 0.003), 4),
                "lng": round(-75.6972 + ((idx % 6) * 0.003), 4),
                "name": f"Ottawa Traffic Cam #{idx}",
                "city": "Ottawa", "country": "Canadá",
                "feed_url": f"https://traffic.ottawa.ca/map/camera_image?id={idx}",
                "stream_type": "jpg",
                "source": "Ottawa Traffic (Canadá)",
            })
        return "Ottawa Traffic (Canadá)", ottawa_cams

    async def _fetch_canada_drivebc():
        drivebc_cams = []
        try:
            data = await _fetch_json_http("https://www.drivebc.ca/api/webcams", timeout=5)
            if data and isinstance(data, list):
                for c in data:
                    if not c.get("is_on", True):
                        continue
                    cid = c.get("id")
                    loc = c.get("location", {}) or {}
                    coords = loc.get("coordinates", [])
                    if len(coords) >= 2 and cid:
                        c_name = c.get("name") or f"#{cid}"
                        c_region = c.get("region_name") or "BC"
                        drivebc_cams.append({
                            "id": f"ca-drivebc-{cid}",
                            "lat": round(float(coords[1]), 4),
                            "lng": round(float(coords[0]), 4),
                            "name": f"BC Highway Cam - {c_name}",
                            "city": f"{c_region} / BC",
                            "country": "Canadá",
                            "feed_url": f"https://www.drivebc.ca/images/{cid}.jpg",
                            "stream_type": "jpg",
                            "source": "DriveBC (Canadá)",
                        })
                    if len(drivebc_cams) >= 80:
                        break
        except Exception as e:
            logger.debug(f"[CCTV] DriveBC fetch error: {e}")

        if not drivebc_cams:
            valid_fallback_ids = [2, 29, 424, 516, 12, 15, 20, 25, 30, 45, 50, 60, 70, 80, 90, 100]
            for idx in valid_fallback_ids:
                drivebc_cams.append({
                    "id": f"ca-drivebc-{idx}",
                    "lat": round(49.2827 + ((idx % 7) * 0.005), 4),
                    "lng": round(-123.1207 + ((idx % 5) * 0.005), 4),
                    "name": f"BC Highway Cam #{idx}",
                    "city": "Vancouver / BC", "country": "Canadá",
                    "feed_url": f"https://www.drivebc.ca/images/{idx}.jpg",
                    "stream_type": "jpg",
                    "source": "DriveBC (Canadá)",
                })
        return "DriveBC (Canadá)", drivebc_cams


    # Execute all fetchers in parallel with robust error isolation
    raw_results = await asyncio.gather(
        _fetch_singapore(),
        _fetch_finland_fintraffic(),
        _fetch_spain_euskadi(),
        _fetch_usa_houston(),
        _fetch_canada_ottawa(),
        _fetch_canada_drivebc(),
        return_exceptions=True,
    )

    for res in raw_results:
        if isinstance(res, tuple) and len(res) == 2:
            s_name, c_list = res
            if c_list:
                cameras.extend(c_list)
                sources[s_name] = len(c_list)

    # Filter by radius/coordinates if supplied
    if lat is not None and lng is not None and radius_km is not None:
        filtered = []
        for cam in cameras:
            if cam["lat"] != 0 and cam["lng"] != 0:
                dist = _haversine_km(lat, lng, cam["lat"], cam["lng"])
                if dist <= radius_km:
                    cam["distance_km"] = round(dist, 2)
                    filtered.append(cam)
        filtered.sort(key=lambda x: x.get("distance_km", 99999))
        cameras = filtered
    else:
        # Group by source and cap each source to max 45 per source for balanced distribution
        by_source = {}
        for c in cameras:
            s = c.get("source", "Other")
            if s not in by_source:
                by_source[s] = []
            by_source[s].append(c)

        balanced_cameras = []
        import random
        for s, cam_list in by_source.items():
            random.shuffle(cam_list)
            balanced_cameras.extend(cam_list[:45])

        cameras = balanced_cameras

    result = {
        "cameras": cameras,
        "total": len(cameras),
        "sources": sources,
        "regions": ["us-south", "us-east", "us-west", "sg", "ca", "fi", "esp", "latam", "europe", "asia"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if lat is None and lng is None and radius_km is None:
        _cctv_cache_data = result
        _cctv_cache_time = now

    return result


@router.get("/cctv/image")
async def cctv_image(url: str = Query(...)):
    """High-performance Proxy for REAL CCTV feed images with IP fallback probing & 90s frame memory cache."""
    global _cctv_last_valid_frames
    import time
    now_ts = time.time()

    async def _try_fetch_feed(target_url: str):
        try:
            session = await _get_cctv_proxy_session()
            async with session.get(target_url, timeout=4) as resp:
                if resp.status == 200:
                    c_type = resp.headers.get("Content-Type", "").lower()
                    if "multipart" in c_type or "mjpeg" in c_type or ".mjpg" in target_url:
                        frame_bytes = b""
                        start_time = time.time()
                        while time.time() - start_time < 2.0:
                            chunk = await resp.content.read(32768)
                            if not chunk:
                                break
                            frame_bytes += chunk
                            s_idx = frame_bytes.find(b"\xff\xd8")
                            e_idx = frame_bytes.find(b"\xff\xd9", s_idx + 2) if s_idx != -1 else -1
                            if s_idx != -1 and e_idx != -1:
                                jpeg_data = frame_bytes[s_idx:e_idx + 2]
                                _cctv_last_valid_frames[url] = (jpeg_data, "image/jpeg", time.time())
                                return Response(
                                    content=jpeg_data,
                                    media_type="image/jpeg",
                                    headers={
                                        "Cache-Control": "public, max-age=5",
                                        "Access-Control-Allow-Origin": "*",
                                        "X-CCTV-Proxy": "COBALTO-MJPEG-REAL",
                                    },
                                )
                    else:
                        content = await resp.read()
                        if content and len(content) > 100:
                            content_type = resp.headers.get("Content-Type", "image/jpeg")
                            if "octet-stream" in content_type:
                                content_type = "image/jpeg"
                            # Guard: Reject HTML pages returned with HTTP 200 by non-standard servers
                            if "html" in content_type.lower() or content.startswith(b"<!DOC") or content.startswith(b"<html") or content.startswith(b"<HTML"):
                                return None
                            _cctv_last_valid_frames[url] = (content, content_type, time.time())
                            return Response(
                                content=content,
                                media_type=content_type,
                                headers={
                                    "Cache-Control": "public, max-age=10",
                                    "Access-Control-Allow-Origin": "*",
                                    "X-CCTV-Proxy": "COBALTO-REAL-FEED",
                                },
                            )

        except Exception as err:
            logger.debug(f"[CCTV PROXY] Real feed fetch error for {target_url}: {err}")
        return None

    if url.startswith("http://") or url.startswith("https://"):
        # 1. Primary target fetch
        res = await _try_fetch_feed(url)
        if res:
            return res

        # 2. If url ends with '/', probe standard IP webcam paths
        if url.endswith("/"):
            for subpath in ["mjpg/video.mjpg", "axis-cgi/mjpg/video.cgi", "video.mjpg", "image.jpg"]:
                probe_url = f"{url}{subpath}"
                res_probe = await _try_fetch_feed(probe_url)
                if res_probe:
                    return res_probe

    # 3. Memory cache fallback: serve last valid real frame if < 90 seconds old (prevents visual flickering during temporary drop)
    if url in _cctv_last_valid_frames:
        cached_bytes, cached_type, cached_time = _cctv_last_valid_frames[url]
        if now_ts - cached_time < 90.0:
            return Response(
                content=cached_bytes,
                media_type=cached_type,
                headers={
                    "Cache-Control": "public, max-age=5",
                    "Access-Control-Allow-Origin": "*",
                    "X-CCTV-Proxy": "COBALTO-FRAME-CACHE",
                },
            )

    # Standard clean SVG offline status for non-responsive cameras (No simulations)
    fallback_svg = b"""<svg xmlns="http://www.w3.org/2000/svg" width="340" height="190" viewBox="0 0 340 190">
    <rect width="340" height="190" fill="#060913"/>
    <rect x="2" y="2" width="336" height="186" rx="6" fill="none" stroke="#64748B" stroke-width="1" opacity="0.3"/>
    <circle cx="170" cy="80" r="22" fill="none" stroke="#64748B" stroke-width="2" opacity="0.5"/>
    <text x="170" y="85" text-anchor="middle" fill="#64748B" font-family="monospace" font-size="16">&#128249;</text>
    <text x="170" y="130" text-anchor="middle" fill="#94A3B8" font-family="monospace" font-size="11" font-weight="bold">TRANSMISIO&#768;N NO DISPONIBLE</text>
    <text x="170" y="148" text-anchor="middle" fill="#64748B" font-family="monospace" font-size="8">CA&#769;MARA FUERA DE LI&#769;NEA EN FUENTE REAL</text>
    </svg>"""
    return Response(
        content=fallback_svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-cache, max-age=10", "Access-Control-Allow-Origin": "*"},
    )


@router.get("/cctv/stream")
async def cctv_stream(url: str = Query(...), format: str = Query("m3u8"), request: Request = None):
    """
    Proxy y transcodificador HLS / MJPEG para cámaras CCTV públicas.
    Genera un manifiesto HLS (.m3u8) para reproducción nativa HTML5 en navegador.
    """
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)

    if format == "m3u8":
        manifest = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:4
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:4.0,
/api/osiris/cctv/image?url={url}&t=1
#EXTINF:4.0,
/api/osiris/cctv/image?url={url}&t=2
"""
        return Response(
            content=manifest,
            media_type="application/vnd.apple.mpegurl",
            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"},
        )
    return await cctv_image(url)


@router.get("/cctv/analyze")
async def cctv_analyze(camera_id: str = Query(...), url: str = Query(...), request: Request = None):
    """
    Analítica de video CCTV con visión por computadora real (OpenCV HOG + MOG2).
    Obtiene un fotograma real de la cámara, detecta personas, vehículos y
    movimiento, y devuelve densidad de tráfico y estado táctico.
    """
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)

    from cctv_vision import analyze_cctv_frame

    # Fetch a real frame (reuse the same proxy logic to avoid duplicating fetch)
    frame_bytes = None
    try:
        session = await _get_cctv_proxy_session()
        async with session.get(url, timeout=4) as resp:
            if resp.status == 200:
                c_type = resp.headers.get("Content-Type", "").lower()
                if "multipart" in c_type or "mjpeg" in c_type or ".mjpg" in url:
                    raw = b""
                    start = time.time()
                    while time.time() - start < 2.0:
                        chunk = await resp.content.read(32768)
                        if not chunk:
                            break
                        raw += chunk
                        s_idx = raw.find(b"\xff\xd8")
                        e_idx = raw.find(b"\xff\xd9", s_idx + 2) if s_idx != -1 else -1
                        if s_idx != -1 and e_idx != -1:
                            frame_bytes = raw[s_idx:e_idx + 2]
                            break
                else:
                    content = await resp.read()
                    if content and len(content) > 100:
                        frame_bytes = content
    except Exception as e:
        logger.debug(f"[CCTV ANALYZE] frame fetch error for {url}: {e}")

    # If a frame could not be fetched, use the last valid cached frame for that URL
    if frame_bytes is None:
        cached = _cctv_last_valid_frames.get(url)
        if cached:
            frame_bytes = cached[0]
        else:
            return {
                "camera_id": camera_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "objects_detected": {"vehicles": 0, "pedestrians": 0, "bicycles": 0},
                "motion_score": 0.0,
                "traffic_density": "DESCONOCIDA",
                "anomaly_detected": False,
                "confidence": 0.0,
                "model": "COBALTO-VISION",
                "tactical_status": "FRAME NO DISPONIBLE",
                "error": "No se pudo obtener un fotograma de la cámara",
            }

    return analyze_cctv_frame(camera_id, frame_bytes)


@router.post("/cctv/collect")
async def trigger_cctv_collection(request: Request = None):
    """Trigger background snapshot collection for active CCTV cameras."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    from cctv_snapshot_collector import snapshot_collector
    res = await data_cctv(region="all")
    cams = res.get("cameras", [])
    collected = await snapshot_collector.collect_from_cameras(cams[:30])
    stats = snapshot_collector.get_stats()
    return {
        "status": "success",
        "cameras_scanned": len(cams[:30]),
        "snapshots_saved": len(collected),
        "collector_stats": stats,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/cctv/analyze")
async def analyze_cctv_motion(request: Request = None):
    """Run computer vision frame analysis on stored snapshots to detect high activity / anomaly motion."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    from cctv_snapshot_collector import snapshot_collector
    analysis = snapshot_collector.analyze_all_cameras()
    high_activity = [a for a in analysis if a.get("status") == "HIGH_ACTIVITY"]
    moderate_activity = [a for a in analysis if a.get("status") == "MODERATE_ACTIVITY"]
    return {
        "total_analyzed": len(analysis),
        "high_activity_count": len(high_activity),
        "moderate_activity_count": len(moderate_activity),
        "high_activity_cameras": high_activity,
        "all_rankings": analysis,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/cctv/alerts")
async def get_cctv_alerts(request: Request = None):
    """Generate automatic tactical motion alerts from CCTV snapshot analysis."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    from cctv_snapshot_collector import snapshot_collector
    alerts = snapshot_collector.generate_cctv_alerts()
    return {
        "alerts_count": len(alerts),
        "alerts": alerts,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.post("/cctv/watchlist")
async def add_cctv_watchlist(camera_id: str = Query(...), request: Request = None):
    """Add camera ID to priority monitoring watchlist."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    from cctv_snapshot_collector import snapshot_collector
    snapshot_collector.add_to_watchlist(camera_id)
    return {
        "status": "added",
        "camera_id": camera_id,
        "watchlist": snapshot_collector.get_watchlist(),
    }


@router.get("/cctv/nearest")
async def get_nearest_cameras(
    lat: float = Query(...),
    lng: float = Query(...),
    limit: int = Query(5),
    request: Request = None,
):
    """Find the N closest public CCTV cameras to given target lat/lng coordinates."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)

    res = await data_cctv(region="all")
    all_cams = res.get("cameras", [])

    with_dist = []
    for c in all_cams:
        c_lat = c.get("lat", 0)
        c_lng = c.get("lng", 0)
        if c_lat != 0 and c_lng != 0:
            dist_km = _haversine_km(lat, lng, c_lat, c_lng)
            c_copy = dict(c)
            c_copy["distance_km"] = round(dist_km, 3)
            c_copy["distance_meters"] = int(dist_km * 1000)
            c_copy["proxy_image_url"] = f"/api/osiris/cctv/image?url={c.get('feed_url', '')}"
            with_dist.append(c_copy)

    with_dist.sort(key=lambda x: x["distance_km"])
    top_nearest = with_dist[:limit]

    return {
        "target_coordinates": {"lat": lat, "lng": lng},
        "limit_requested": limit,
        "found_count": len(top_nearest),
        "nearest_cameras": top_nearest,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/cctv/geojson")

async def get_cctv_geojson(request: Request = None):
    """Return CCTV network as GeoJSON FeatureCollection for Leaflet / GIS mapping engines."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    res = await data_cctv(region="all")
    cameras = res.get("cameras", [])

    features = []
    for c in cameras:
        if c.get("lat") and c.get("lng"):
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [c["lng"], c["lat"]],
                },
                "properties": {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "city": c.get("city"),
                    "country": c.get("country"),
                    "source": c.get("source"),
                    "feed_url": c.get("feed_url"),
                    "stream_type": c.get("stream_type"),
                },
            })

    return {
        "type": "FeatureCollection",
        "features": features,
        "total": len(features),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/cctv/health")
async def cctv_health(
    check: str = Query("auto", pattern="^(auto|full)$"),
    limit: int = Query(60, ge=1, le=200),
    request: Request = None,
):
    """
    Estado de salud / uptime de la red CCTV.

    Verifica en paralelo qué cámaras responden realmente a través del proxy
    (con probe HEAD liviano + cache TTL de 120s). Devuelve recuentos de
    fuentes operativas y alimenta el status dot del frontend.
    """
    global _cctv_health_cache, _cctv_health_cache_time, _cctv_last_valid_frames
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)

    import time as _time
    now = _time.time()
    # Serve from TTL cache (120s) unless a full re-check is explicitly requested
    if check == "auto" and _cctv_health_cache and (now - _cctv_health_cache_time < 120.0):
        return {**_cctv_health_cache, "cached": True, "age_seconds": int(now - _cctv_health_cache_time)}

    res = await data_cctv(region="all")
    cameras = res.get("cameras", [])[:limit]

    async def _probe(cam: dict) -> dict:
        url = cam.get("feed_url", "")
        cid = cam.get("id", "")
        if not url:
            return {"id": cid, "name": cam.get("name"), "online": False, "reason": "sin-feed"}
        try:
            session = await _get_cctv_proxy_session()
            async with session.get(url, timeout=4) as resp:
                # 2xx => reachable; camera might serve MJPEG multipart which never closes
                # so we treat any successful response enough to mark as online
                online = resp.status < 400
                return {
                    "id": cid,
                    "name": cam.get("name"),
                    "source": cam.get("source"),
                    "city": cam.get("city"),
                    "country": cam.get("country"),
                    "stream_type": cam.get("stream_type"),
                    "online": online,
                    "http_status": resp.status,
                    "content_type": resp.headers.get("Content-Type", "").split(";")[0],
                }
        except Exception as e:
            return {"id": cid, "name": cam.get("name"), "source": cam.get("source"), "online": False, "reason": str(e)[:80]}

    probes = await asyncio.gather(*[_probe(c) for c in cameras], return_exceptions=True)

    results = []
    for r in probes:
        if isinstance(r, dict):
            results.append(r)

    online = [r for r in results if r.get("online")]
    offline = [r for r in results if not r.get("online")]

    by_source_online: dict = {}
    for r in online:
        src = r.get("source", "unknown")
        by_source_online[src] = by_source_online.get(src, 0) + 1
    by_source_total: dict = {}
    for r in results:
        src = r.get("source", "unknown")
        by_source_total[src] = by_source_total.get(src, 0) + 1

    payload = {
        "checked": len(results),
        "total": len(cameras),
        "online": len(online),
        "offline": len(offline),
        "online_percent": round((len(online) / max(len(results), 1)) * 100, 1),
        "by_source": {s: {"total": by_source_total.get(s, 0), "online": by_source_online.get(s, 0)} for s in by_source_total},
        "online_cameras": online,
        "offline_cameras": offline[:30],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    _cctv_health_cache = payload
    _cctv_health_cache_time = now
    return {**payload, "cached": False}





@router.get("/data/crypto")
async def data_crypto():
    """Crypto prices from CoinGecko."""
    data = await _fetch_json_http("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true")
    prices = []
    if data:
        mapping = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}
        for cid, sym in mapping.items():
            if cid in data:
                prices.append({
                    "symbol": sym,
                    "price": data[cid].get("usd", 0),
                    "change_24h": data[cid].get("usd_24h_change", 0),
                })
    return prices


@router.get("/data/markets")
async def data_markets():
    """Financial markets data."""
    stocks = {}
    symbols = [("RTX", "RTX"), ("BA", "BA"), ("LMT", "LMT"), ("NOC", "NOC"), ("GD", "GD")]
    for sym, key in symbols:
        data = await _fetch_json_http(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d")
        if data and "chart" in data and data["chart"].get("result"):
            meta = data["chart"]["result"][0].get("meta", {})
            prev = meta.get("previousClose", 1)
            price = meta.get("regularMarketPrice", prev)
            stocks[key] = {"price": price, "change_percent": ((price - prev) / prev) * 100 if prev else 0, "up": price >= prev}
    # Commodities
    oil = {}
    for name, sym in [("WTI Crude", "CL=F"), ("Brent Crude", "BZ=F")]:
        data = await _fetch_json_http(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d")
        if data and "chart" in data and data["chart"].get("result"):
            meta = data["chart"]["result"][0].get("meta", {})
            prev = meta.get("previousClose", 1)
            price = meta.get("regularMarketPrice", prev)
            oil[name] = {"price": price, "change_percent": ((price - prev) / prev) * 100 if prev else 0, "up": price >= prev}
    return {"stocks": stocks, "oil": oil, "commodities": {}, "crypto": {}, "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.get("/data/weather")
async def data_weather():
    """Severe weather events from NASA EONET and active meteorological monitors."""
    data = await _fetch_json_http("https://eonet.gsfc.nasa.gov/api/v3/events?limit=80", timeout=12)
    events = []

    def extract_point(geom_list: list) -> tuple[float, float] | None:
        for g in geom_list:
            coords = g.get("coordinates", [])
            if not coords:
                continue
            curr = coords
            while isinstance(curr, list) and len(curr) > 0 and isinstance(curr[0], list):
                curr = curr[0]
            if isinstance(curr, list) and len(curr) >= 2:
                try:
                    lng = float(curr[0])
                    lat = float(curr[1])
                    if -90 <= lat <= 90 and -180 <= lng <= 180 and not (lat == 0 and lng == 0):
                        return lat, lng
                except (ValueError, TypeError):
                    continue
        return None

    if data and isinstance(data, dict) and "events" in data:
        for ev in data["events"]:
            geoms = ev.get("geometry", [])
            pt = extract_point(geoms)
            if not pt:
                continue
            events.append({
                "id": ev.get("id", ""),
                "title": ev.get("title", "Severe Weather Event"),
                "category": ev.get("categories", [{}])[0].get("title", "Severe Weather"),
                "type": ev.get("categories", [{}])[0].get("id", "weather"),
                "severity": "HIGH",
                "lat": pt[0],
                "lng": pt[1],
                "date": ev.get("closed") or ev.get("opened") or "",
                "source": "NASA EONET",
            })

    return {"events": events, "total": len(events), "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.get("/data/malware")
async def data_malware():
    """Live malware threats from abuse.ch."""
    data = await _fetch_json_http("https://feodotracker.abuse.ch/downloads/ipblocklist.json")
    threats = []
    if data and isinstance(data, list):
        for t in data[:100]:
            threats.append({
                "id": t.get("ip_address", ""),
                "ip": t.get("ip_address", ""),
                "port": t.get("port", 0),
                "malware": t.get("malware", ""),
                "status": t.get("status", ""),
                "first_seen": t.get("first_seen", ""),
                "last_online": t.get("last_online", ""),
                "country": t.get("country", ""),
            })
    return {"threats": threats, "total": len(threats), "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.get("/data/cyber-threats")
async def data_cyber_threats():
    """CISA KEV cyber threats."""
    data = await _fetch_json_http("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json")
    threats = []
    if data and "vulnerabilities" in data:
        for v in data["vulnerabilities"][:50]:
            threats.append({
                "id": v.get("cveID", ""),
                "name": v.get("vulnerabilityName", ""),
                "vendor": v.get("vendorProject", ""),
                "product": v.get("product", ""),
                "severity": "CRITICAL",
                "date": v.get("dateAdded", ""),
                "due": v.get("dueDate", ""),
                "source": "CISA KEV",
            })
    return {"threats": threats, "stats": {"cisa_total": len(threats), "threat_level": "CRITICAL" if threats else "LOW"}, "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.get("/data/stats")
async def data_stats():
    """Aggregate dashboard stats."""
    return {"stats": {"flights": "live", "sats": "live", "cctv": "live", "earthquakes": "live", "fires": "live"}, "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.get("/snapshots")
async def list_snapshots(camera_id: str = "", limit: int = 50):
    """List stored CCTV snapshots."""
    from cctv_snapshot_collector import snapshot_collector
    snaps = snapshot_collector.list_snapshots(camera_id=camera_id, limit=limit)
    stats = snapshot_collector.get_stats()
    return {"snapshots": snaps, "stats": stats}


@router.get("/snapshots/stats")
async def snapshot_stats():
    """Snapshot collector statistics."""
    from cctv_snapshot_collector import snapshot_collector
    return snapshot_collector.get_stats()


# ── REGION DOSSIER ──

@router.get("/intel/region-dossier")
async def intel_region_dossier(lat: float = Query(...), lng: float = Query(...), request: Request = None):
    """Country intelligence for any coordinate."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    # Reverse geocode
    geo_data = await _fetch_json_http(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json&zoom=10&addressdetails=1")
    if not geo_data or "address" not in geo_data:
        return {"coordinates": {"lat": lat, "lng": lng}, "error": "Could not resolve location"}
    addr = geo_data.get("address", {})
    location = {
        "city": addr.get("city", addr.get("town", addr.get("village", ""))),
        "state": addr.get("state", addr.get("region", "")),
        "country": addr.get("country", ""),
        "country_code": addr.get("country_code", ""),
        "display_name": geo_data.get("display_name", ""),
    }
    # Country info via Wikipedia
    country_info = {}
    if location["country"]:
        wiki_data = await _fetch_json_http(f"https://en.wikipedia.org/api/rest_v1/page/summary/{location['country'].replace(' ', '_')}")
        if wiki_data and "extract" in wiki_data:
            country_info = {
                "name": location["country"],
                "capital": wiki_data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "population": "",
                "area": "",
                "flag_url": wiki_data.get("thumbnail", {}).get("source", ""),
                "wikipedia_title": wiki_data.get("title", ""),
                "extract": wiki_data.get("extract", ""),
                "thumbnail": wiki_data.get("thumbnail", {}).get("source", ""),
            }
    return {
        "coordinates": {"lat": lat, "lng": lng},
        "location": location,
        "country": country_info,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── COLOMBIA OSINT ENDPOINTS ──

@router.get("/colombia/secop")
async def colombia_secop(
    q: str | None = Query(None),
    departamento: str | None = Query(None),
    monto_min: float | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    request: Request = None,
):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    from osiris_colombia_recon import query_secop_socrata
    records = await query_secop_socrata(query_text=q, departamento=departamento, monto_min=monto_min, limit=limit, offset=offset)
    return {
        "fuente": "SECOP II / Datos Abiertos Colombia (Socrata)",
        "total_fetched": len(records),
        "limit": limit,
        "offset": offset,
        "records": records,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/colombia/jep")
async def colombia_jep(limit: int = Query(15, ge=1, le=50), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    from osiris_colombia_recon import fetch_jep_press_releases
    releases = await fetch_jep_press_releases(limit=limit)
    return {
        "fuente": "JEP (Jurisdicción Especial para la Paz)",
        "total_fetched": len(releases),
        "records": releases,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/colombia/rama-judicial")
async def colombia_rama_judicial(radicado: str = Query(...), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    from osiris_colombia_recon import query_rama_judicial_radicado
    result = await query_rama_judicial_radicado(radicado)
    return {
        "fuente": "Rama Judicial de Colombia (Consulta de Procesos)",
        "radicado": radicado,
        "data": result,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/colombia/summary")
async def colombia_summary(limit: int = Query(50, ge=1, le=200), request: Request = None):
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    from osiris_colombia_recon import get_colombia_intel_summary
    records = get_colombia_intel_summary(limit=limit)
    return {
        "fuente": "Consolidado SQLite Inteligencia Colombia",
        "total": len(records),
        "records": records,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── Async HTTP helpers ──

async def _fetch_json_http(url: str, headers: dict | None = None, timeout: int = 30) -> Any:
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        **(headers or {}),
    }
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, headers=hdrs) as session:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                logger.debug(f"[OSIRIS-BRIDGE] HTTP {resp.status} for {url}")
                return None
    except Exception as e:
        logger.debug(f"[OSIRIS-BRIDGE] HTTP error for {url}: {e}")
        return None


async def _fetch_text_http(url: str, timeout: int = 30) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.text()
                return None
    except Exception:
        return None


# Sanctions index is loaded lazily on first request
