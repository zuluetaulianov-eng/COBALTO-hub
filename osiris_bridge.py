"""
osiris_bridge.py — OSIRIS Feature Bridge for COBALTO HUB
Ports all OSIRIS API endpoints as FastAPI routes under /api/osiris/
"""
import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Any

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
    cve_lookup,
    dns_lookup,
    github_lookup,
    http_headers,
    ip_intel,
    ip_sweep,
    leaks_lookup,
    mac_lookup,
    phone_lookup,
    shodan_lookup,
    ssl_check,
    threats_lookup,
    whois_lookup,
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


def _get_client_ip(request: Request) -> str:
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "127.0.0.1")
    return ip.split(",")[0].strip()


# ── Health ──
@router.get("/health")
async def osiris_health():
    return {
        "status": "ok",
        "platform": "OSIRIS-on-COBALTO",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


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
    """Satellite tracking data from Celestrak."""
    groups = ["active", "starlink", "gps-ops", "geo", "science", "stations"]
    async def fetch_group(group: str) -> list[dict]:
        url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=json"
        data = await _fetch_json_http(url)
        if isinstance(data, list):
            return [{
                "name": s.get("OBJECT_NAME", "").strip(),
                "lat": s.get("LAT", 0),
                "lng": s.get("LON", 0),
                "alt": s.get("ALT", 0),
                "mission": group,
                "noradId": s.get("NORAD_CAT_ID", ""),
                "category": group,
            } for s in data[:500]]
        return []
    results = await asyncio.gather(*[fetch_group(g) for g in groups])
    all_sats = [s for r in results for s in r]
    cat_counts = {}
    for g in groups:
        cat_counts[g] = sum(1 for s in all_sats if s["mission"] == g)
    return {
        "satellites": all_sats,
        "total": len(all_sats),
        "category_counts": cat_counts,
        "source": "celestrak",
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


@router.get("/data/cctv")
async def data_cctv(region: str = Query("all"), request: Request = None):
    """Worldwide CCTV cameras from public feeds."""
    if not _check_rate_limit(_get_client_ip(request)):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    cameras = []
    sources = {}
    # TfL London
    tfl = await _fetch_json_http("https://api.tfl.gov.uk/Place/Type/JamCam")
    if tfl and isinstance(tfl, list):
        for c in tfl[:100]:
            cid = c.get('id', '')
            lat = c.get("lat", 0)
            lng = c.get("lon", 0)
            if not cid or not lat or not lng: continue
            cameras.append({
                "id": f"tfl-{cid}",
                "lat": lat, "lng": lng,
                "name": c.get("commonName", "TfL Camera"),
                "city": "London", "country": "UK",
                "feed_url": f"https://s3-eu-west-1.amazonaws.com/jamcams.tfl.gov.uk/{cid}.jpg",
                "stream_type": "jpg",
                "source": "TfL",
            })
        sources["TfL"] = len(cameras)
    # WSDOT Washington
    wsdot = await _fetch_json_http("https://data.wsdot.wa.gov/log/public/cameras.json")
    if wsdot and isinstance(wsdot, list):
        cc = 0
        for c in wsdot[:100]:
            cams = c.get("Cameras", [])
            for cam in cams:
                feed_url = cam.get("ImageUrl", "")
                lat = cam.get("Latitude", 0)
                lng = cam.get("Longitude", 0)
                if not feed_url or not lat or not lng: continue
                cameras.append({
                    "id": f"wsdot-{c.get('Id', '')}_{cam.get('Id', '')}",
                    "lat": lat, "lng": lng,
                    "name": c.get("Title", cam.get("Description", "WSDOT Camera")),
                    "city": c.get("Title", ""), "country": "USA",
                    "feed_url": feed_url,
                    "stream_type": "jpg",
                    "source": "WSDOT",
                })
                cc += 1
        sources["WSDOT"] = cc
    # Singapore
    sg = await _fetch_json_http("https://api.data.gov.sg/v1/transport/traffic-images")
    if sg and isinstance(sg, dict):
        cc = 0
        for item in sg.get("items", []):
            for cam in item.get("cameras", [])[:80]:
                loc = cam.get("location", {})
                feed_url = cam.get("image", "")
                lat = loc.get("latitude", 0)
                lng = loc.get("longitude", 0)
                if not feed_url or not lat or not lng: continue
                cameras.append({
                    "id": f"sg-{cam.get('camera_id', '')}",
                    "lat": lat, "lng": lng,
                    "name": f"Singapore {cam.get('camera_id', '')}",
                    "city": "Singapore", "country": "Singapore",
                    "feed_url": feed_url,
                    "stream_type": "jpg",
                    "source": "Singapore LTA",
                })
                cc += 1
            break
        sources["Singapore"] = cc
    # Venezuela — OpenStreetMap webcams (Overpass API)
    try:
        overpass_query = "[out:json];area[\"name\"=\"Venezuela\"]->.a;node[\"amenity\"=\"webcam\"](area.a);out body;"
        ve_cams = await _fetch_json_http(
            "https://overpass-api.de/api/interpreter?data=" + overpass_query,
        )
        if ve_cams and isinstance(ve_cams, dict):
            elements = ve_cams.get("elements", [])
            cc = 0
            for el in elements:
                lat = el.get("lat", 0)
                lng = el.get("lon", 0)
                tags = el.get("tags", {})
                feed_url = tags.get("url", "") or tags.get("image_url", "") or tags.get("video_url", "")
                name = tags.get("name", tags.get("operator", "OSM Webcam"))
                if not lat or not lng:
                    continue
                cameras.append({
                    "id": f"osm-ve-{el.get('id', '')}",
                    "lat": lat, "lng": lng,
                    "name": name,
                    "city": tags.get("city", tags.get("addr:city", "")),
                    "country": "Venezuela",
                    "feed_url": feed_url,
                    "stream_type": "jpg",
                    "source": "OpenStreetMap",
                })
                cc += 1
            sources["Venezuela-OSM"] = cc
    except Exception:
        pass
    # Venezuela — Insecam scraper
    try:
        import aiohttp
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get("http://insecam.org/en/jsoncountries/", headers={"User-Agent": "Mozilla/5.0"}) as resp:
                countries = await resp.json()
            ve_key = None
            for c in countries:
                if c.get("country", "").lower() == "venezuela" or c.get("c", "") == "VE":
                    ve_key = c.get("c", c.get("country"))
                    break
            if ve_key:
                async with session.get(
                    f"http://insecam.org/en/json/VE/",
                    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                ) as resp:
                    ve_data = await resp.json()
                ve_cams_list = ve_data if isinstance(ve_data, list) else ve_data.get("cameras", [])
                cc = 0
                for cam in ve_cams_list[:50]:
                    ip = cam.get("ip", "") or cam.get("host", "")
                    port = cam.get("port", "80")
                    lat = cam.get("lat", 0) or cam.get("latitude", 0)
                    lng = cam.get("lng", 0) or cam.get("longitude", 0)
                    if not ip:
                        continue
                    feed_url = f"http://{ip}:{port}/"
                    name = cam.get("name", cam.get("title", f"Camera {ip}"))
                    cameras.append({
                        "id": f"insecam-ve-{ip.replace('.', '-')}-{port}",
                        "lat": float(lat) if lat else 0,
                        "lng": float(lng) if lng else 0,
                        "name": name,
                        "city": cam.get("city", ""),
                        "country": "Venezuela",
                        "feed_url": feed_url,
                        "stream_type": "mjpeg",
                        "source": "Insecam",
                    })
                    cc += 1
                sources["Venezuela-Insecam"] = cc
    except Exception:
        pass
    # Random sample to avoid cluttering
    import random
    random.shuffle(cameras)
    cameras = cameras[:120]
    return {
        "cameras": cameras,
        "total": len(cameras),
        "sources": sources,
        "regions": ["uk", "us-west", "sg", "ve"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/cctv/image")
async def cctv_image(url: str = Query(...)):
    """Proxy for CCTV feed images. Fetches the image server-side and returns it."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    content_type = resp.headers.get("Content-Type", "image/jpeg")
                    return Response(content=content, media_type=content_type,
                                    headers={"Cache-Control": "public, max-age=30", "Access-Control-Allow-Origin": "*"})
    except Exception:
        pass
    # Return a visible placeholder SVG when the feed cannot be fetched
    fallback_svg = b"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">
    <rect width="320" height="180" fill="#0A0B10"/>
    <rect x="1" y="1" width="318" height="178" rx="4" fill="none" stroke="#333" stroke-width="1"/>
    <circle cx="160" cy="70" r="20" fill="none" stroke="#FF4444" stroke-width="2" opacity="0.6"/>
    <text x="160" y="120" text-anchor="middle" fill="#FF4444" font-family="monospace" font-size="11" opacity="0.8">CAMERA OFFLINE</text>
    <text x="160" y="140" text-anchor="middle" fill="#555" font-family="monospace" font-size="8">feed unreachable</text>
    </svg>"""
    return Response(content=fallback_svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "no-cache, max-age=60", "Access-Control-Allow-Origin": "*"})


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
    """Severe weather events from NASA EONET."""
    data = await _fetch_json_http("https://eonet.gsfc.nasa.gov/api/v3/events")
    events = []
    if data and "events" in data:
        for ev in data["events"][:50]:
            for geom in ev.get("geometry", []):
                coords = geom.get("coordinates", [0, 0])
                events.append({
                    "id": ev.get("id", ""),
                    "title": ev.get("title", ""),
                    "category": ev.get("categories", [{}])[0].get("title", ""),
                    "type": ev.get("categories", [{}])[0].get("id", ""),
                    "severity": "HIGH",
                    "lat": coords[1] if len(coords) > 1 else 0,
                    "lng": coords[0] if len(coords) > 0 else 0,
                    "date": ev.get("closed", ev.get("opened", "")),
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


# ── Async HTTP helpers ──

async def _fetch_json_http(url: str, headers: dict | None = None, timeout: int = 30) -> Any:
    hdrs = {"User-Agent": "COBALTO-OSIRIS/1.0", **(headers or {})}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=hdrs, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
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
