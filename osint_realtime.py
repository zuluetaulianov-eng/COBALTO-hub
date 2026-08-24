# osint_realtime.py - Módulo de Inteligencia en Tiempo Real
# Fuentes especializadas: IODA, Dólar, ACLED, ADS-B, ReliefWeb,
# Exploit-DB, BGPView, OVF, Gaceta Oficial, VesselFinder
# Todas gratuitas, sin instalación adicional.

import logging
import os
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlencode

import feedparser
import urllib3
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from config import REGIONAL_BBOX, TRACKING_AIRCRAFT
from utils import safe_get

logger = logging.getLogger(__name__)

load_dotenv()
urllib3.disable_warnings()

# ════════════════════════════════════════════════════════════════
# 1. IODA — Detección de apagones de internet en Venezuela
#    API pública de Georgia Tech / CAIDA. Sin clave.
# ════════════════════════════════════════════════════════════════
IODA_BASE = "https://api.ioda.inetintel.cc.gatech.edu/v2"

# Códigos de Venezuela en IODA
# country=VE | ASNs de CANTV=8048, Movistar=6306, Inter=21826, Digitel=11479
VE_ASNS = {
    "CANTV": "8048",
    "Movistar": "6306",
    "Inter": "21826",
    "Digitel": "11479",
}


def get_ioda_outages() -> List[Dict[str, Any]]:
    """Detecta cortes de internet activos en Venezuela vía IODA."""
    results = []
    try:
        # Estado actual del país
        url = f"{IODA_BASE}/signals/raw/country/VE"
        resp = safe_get(url)
        if resp.status_code != 200:
            return results

        data = resp.json()
        signals = data.get("data", {})

        # Analizar señales — umbral bajo indica posible corte
        for signal_type, signal_data in signals.items():
            if not isinstance(signal_data, list) or not signal_data:
                continue
            latest = signal_data[-1]
            value = latest.get("val", 1.0)
            # Si el valor normalizado cae bajo 0.7, es anomalía
            if isinstance(value, (int, float)) and value < 0.7:
                severity = "CRÍTICO" if value < 0.3 else "ADVERTENCIA"
                results.append(
                    {
                        "title": f"[IODA] {severity}: Anomalía de conectividad en Venezuela ({signal_type})",
                        "summary": f"Señal {signal_type} en {value * 100:.1f}% — posible corte de internet detectado. Fuente: IODA/Georgia Tech.",
                        "link": "https://ioda.live/country/VE",
                        "published": datetime.now().isoformat(),
                        "source": "🌐 IODA Internet Monitor",
                        "type": "ioda_outage",
                    }
                )

        if not results:
            results.append(
                {
                    "title": "IODA: Conectividad Venezuela — Normal",
                    "summary": "No se detectan anomalías significativas en la conectividad de Venezuela en este momento.",
                    "link": "https://ioda.live/country/VE",
                    "published": datetime.now().isoformat(),
                    "source": "🌐 IODA Internet Monitor",
                    "type": "ioda_ok",
                }
            )

    except Exception as e:
        logger.warning(f"IODA: {e}")
    return results


_bgpview_cb = {"disabled": False}


def get_bgpview_ve() -> List[Dict[str, Any]]:
    """Estado BGP de los principales ISPs de Venezuela."""
    results = []
    if _bgpview_cb["disabled"]:
        return results
    for isp, asn in VE_ASNS.items():
        try:
            url = f"https://api.bgpview.io/asn/{asn}/prefixes"
            resp = safe_get(url, timeout=8)
            if resp is not None and resp.status_code == 200:
                data = resp.json()
                prefixes = data.get("data", {}).get("ipv4_prefixes", [])
                results.append(
                    {
                        "title": f"BGP {isp} (AS{asn}): {len(prefixes)} prefijos IPv4 activos",
                        "summary": f"El ISP {isp} anuncia {len(prefixes)} bloques de IPs. Si cae a 0 es señal de corte total.",
                        "link": f"https://bgpview.io/asn/{asn}",
                        "published": datetime.now().isoformat(),
                        "source": f"📡 BGPView ({isp})",
                        "type": "bgp",
                    }
                )
            else:
                logger.warning(
                    f"BGPView {isp} returned status {getattr(resp, 'status_code', 'N/A')}. Desactivando consultas BGP."
                )
                _bgpview_cb["disabled"] = True
                break
        except Exception as e:
            logger.warning(f"BGPView {isp} error: {e}. Desactivando consultas BGP.")
            _bgpview_cb["disabled"] = True
            break
    return results


# ════════════════════════════════════════════════════════════════
# 2. MONITOR DÓLAR — Tasas de cambio Venezuela
#    API JSON pública, sin clave, actualización cada hora.
# ════════════════════════════════════════════════════════════════
DOLAR_API = "https://ve.dolarapi.com/v1/dolares"


def get_dolar_rates() -> List[Dict[str, Any]]:
    """Obtiene todas las tasas de cambio de Venezuela: BCV, paralelo, cripto."""
    results = []
    try:
        resp = safe_get(DOLAR_API)
        if resp.status_code == 200:
            datos = resp.json()
            for item in datos:
                nombre = item.get("nombre", "")
                fuente = item.get("fuente", "")
                promedio = item.get("promedio", 0)
                fecha = item.get("fechaActualizacion", datetime.now().isoformat())

                # Calcular diferencia porcentual con BCV si hay dato
                results.append(
                    {
                        "title": f"💵 {nombre}: Bs. {promedio:,.2f}",
                        "summary": f"Fuente: {fuente} | Actualizado: {str(fecha)[:16]}",
                        "link": "https://ve.dolarapi.com",
                        "published": str(fecha),
                        "source": f"Monitor Dólar ({fuente})",
                        "type": "dolar",
                    }
                )
    except Exception as e:
        logger.warning(f"DolarAPI: {e}")
    return results


# ════════════════════════════════════════════════════════════════
# 3. ACLED — Eventos de conflicto armado con coordenadas GPS
#    API pública gratuita. Requiere clave (registro en acleddata.com).
#    Sin clave: usa fuente alternativa de datos públicos.
# ════════════════════════════════════════════════════════════════
ACLED_KEY = os.getenv("ACLED_KEY")  # Registrarse gratis en acleddata.com
ACLED_EMAIL = os.getenv("ACLED_EMAIL")  # Añadir en .env para activar


def get_acled_venezuela() -> List[Dict[str, Any]]:
    """Eventos de conflicto armado en Venezuela (ACLED)."""
    results = []

    if ACLED_KEY and ACLED_EMAIL:
        try:
            url = "https://api.acleddata.com/acled/read"
            params = {
                "key": ACLED_KEY,
                "email": ACLED_EMAIL,
                "country": "Venezuela",
                "limit": 20,
                "fields": "event_date|event_type|sub_event_type|actor1|location|admin1|fatalities|notes|latitude|longitude",
            }
            resp = safe_get(f"{url}?{urlencode(params)}")
            if resp.status_code == 200:
                data = resp.json()
                for ev in data.get("data", []):
                    fatalities = int(ev.get("fatalities", 0))
                    results.append(
                        {
                            "title": f"[ACLED] {ev.get('event_type')}: {ev.get('location')}, {ev.get('admin1')}",
                            "summary": f"{ev.get('notes', '')[:200]} | Actor: {ev.get('actor1')} | Bajas: {fatalities}",
                            "link": "https://acleddata.com/data-export-tool/",
                            "published": ev.get("event_date", datetime.now().isoformat()),
                            "source": "⚔️ ACLED Conflict Monitor",
                            "type": "acled",
                            "latitude": ev.get("latitude"),
                            "longitude": ev.get("longitude"),
                        }
                    )
        except Exception as e:
            logger.warning(f"ACLED: {e}")
    else:
        # Sin clave: fuente alternativa via ReliefWeb/UNHCR
        results.append(
            {
                "title": "ACLED: Configurar clave gratuita para activar",
                "summary": "Registrate gratis en acleddata.com y añade ACLED_KEY y ACLED_EMAIL en osint_realtime.py para activar el mapa de conflictos.",
                "link": "https://acleddata.com/register/",
                "published": datetime.now().isoformat(),
                "source": "⚔️ ACLED (sin activar)",
                "type": "acled_info",
            }
        )
    return results


# ════════════════════════════════════════════════════════════════
# 4. ADS-B EXCHANGE — Tracking de vuelos Regional
# ════════════════════════════════════════════════════════════════
ADSB_API = "https://opendata.adsb.fi/api/v2"


def get_adsb_venezuela() -> List[Dict[str, Any]]:
    """Vuelos activos sobre espacio aéreo regional (ADS-B)."""
    results = []
    try:
        # adsb.fi es la API pública sin clave de ADS-B Exchange
        url = (
            f"{ADSB_API}/lat/{(REGIONAL_BBOX['lat_min'] + REGIONAL_BBOX['lat_max']) / 2}"
            f"/lon/{(REGIONAL_BBOX['lon_min'] + REGIONAL_BBOX['lon_max']) / 2}/dist/800"
        )
        resp = safe_get(url)
        if resp.status_code == 200:
            data = resp.json()
            aircraft_list = data.get("ac", [])

            # Filtrar solo los que están dentro del bounding box
            ve_aircraft = [
                a
                for a in aircraft_list
                if (
                    isinstance(a.get("lat"), (int, float))
                    and isinstance(a.get("lon"), (int, float))
                    and REGIONAL_BBOX["lat_min"] <= a["lat"] <= REGIONAL_BBOX["lat_max"]
                    and REGIONAL_BBOX["lon_min"] <= a["lon"] <= REGIONAL_BBOX["lon_max"]
                )
            ]

            if ve_aircraft:
                # Guardar cada aeronave con coordenadas individuales para el mapa
                for a in ve_aircraft:
                    flight_id = a.get("flight", "").strip() or a.get("icao", a.get("id", "N/A"))
                    icao24 = a.get("icao", "").upper()
                    aircraft_type = a.get("t", "?")
                    is_military = a.get("mil", False)

                    # Detección de objetivos de alto interés
                    is_high_interest = icao24 in TRACKING_AIRCRAFT
                    if is_high_interest:
                        title = f"🚨 ALERTA: {TRACKING_AIRCRAFT[icao24]} Detectado"
                        priority = "CRÍTICO"
                    else:
                        title = f"✈️ {flight_id} ({aircraft_type})"
                        priority = "MILITAR" if is_military else "CIVIL"

                    results.append(
                        {
                            "title": title,
                            "summary": f"Altitud: {a.get('alt', 'N/A')}ft | Velocidad: {a.get('gs', 'N/A')}kts | {priority}",
                            "link": f"https://globe.adsbexchange.com/?icao={icao24}",
                            "published": datetime.now().isoformat(),
                            "source": "✈️ ADS-B" + (" TÁCTICO" if is_high_interest else ""),
                            "type": "adsb_high_interest"
                            if is_high_interest
                            else ("adsb_military" if is_military else "adsb"),
                            "latitude": a.get("lat"),
                            "longitude": a.get("lon"),
                        }
                    )
            else:
                results.append(
                    {
                        "title": "ADS-B: Sin aeronaves detectadas sobre Venezuela",
                        "summary": "No hay transponders ADS-B activos en espacio aéreo venezolano en este momento.",
                        "link": "https://globe.adsbexchange.com/?lat=7.5&lon=-66&zoom=5",
                        "published": datetime.now().isoformat(),
                        "source": "✈️ ADS-B Exchange",
                        "type": "adsb",
                    }
                )
    except Exception as e:
        logger.warning(f"ADS-B: {e}")
    return results


# ════════════════════════════════════════════════════════════════
# 5. RELIEFWEB — Reportes humanitarios ONU sobre Venezuela
#    API pública REST sin clave.
# ════════════════════════════════════════════════════════════════
RELIEFWEB_API = "https://api.reliefweb.int/v1"


def get_reliefweb_venezuela() -> List[Dict[str, Any]]:
    """Reportes humanitarios y crisis de Venezuela desde ReliefWeb (ONU)."""
    results = []
    try:
        url = f"{RELIEFWEB_API}/reports"
        params = {
            "appname": "CobaltoHub",
            "filter[field]": "country.iso3",
            "filter[value]": "VEN",
            "limit": 8,
            "sort[]": "date:desc",
            "fields[include][]": "title,date,url,body-html,source",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        resp = safe_get(f"{url}?{query}")
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("data", []):
                fields = item.get("fields", {})
                date_info = fields.get("date", {})
                pub_date = (
                    date_info.get("original", datetime.now().isoformat())
                    if isinstance(date_info, dict)
                    else str(date_info)
                )
                sources = fields.get("source", [])
                src_name = sources[0].get("name", "ReliefWeb") if sources else "ReliefWeb"
                results.append(
                    {
                        "title": fields.get("title", "Sin título")[:140],
                        "summary": BeautifulSoup(fields.get("body-html", ""), "html.parser").get_text()[:280],
                        "link": fields.get("url", "https://reliefweb.int"),
                        "published": pub_date[:10],
                        "source": f"🆘 ReliefWeb ({src_name})",
                        "type": "reliefweb",
                    }
                )
    except Exception as e:
        logger.warning(f"ReliefWeb: {e}")
    return results


# ════════════════════════════════════════════════════════════════
# 6. EXPLOIT-DB — RSS de CVEs y exploits (OSINT ciberseguridad)
# ════════════════════════════════════════════════════════════════
def get_exploitdb() -> List[Dict[str, Any]]:
    """Últimas vulnerabilidades publicadas en Exploit-DB."""
    results = []
    try:
        resp = safe_get("https://www.exploit-db.com/rss.xml")
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:6]:
            results.append(
                {
                    "title": entry.get("title", "Sin título")[:140],
                    "summary": entry.get("summary", "")[:280],
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", datetime.now().isoformat()),
                    "source": "🔓 Exploit-DB",
                    "type": "exploit",
                }
            )
    except Exception as e:
        logger.warning(f"Exploit-DB: {e}")
    return results


# ════════════════════════════════════════════════════════════════
# 7. OVF — Observatorio Venezolano de Finanzas (scraping)
# ════════════════════════════════════════════════════════════════
def get_ovf_data() -> List[Dict[str, Any]]:
    """Scraping del OVF: inflación, escasez, liquidez, reservas."""
    results = []
    try:
        resp = safe_get("https://observatoriodefinanzas.com/")
        if resp.status_code != 200:
            return results
        soup = BeautifulSoup(resp.content, "html.parser")

        # Buscar tarjetas de indicadores en la portada
        cards = soup.find_all(
            ["article", "div"], class_=lambda c: c and any(k in c for k in ["card", "indicador", "post", "entry"])
        )[:10]

        for card in cards:
            title_tag = card.find(["h2", "h3", "h4", "a"])
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)[:140]
            if not title or len(title) < 10:
                continue
            link_tag = card.find("a", href=True)
            link = link_tag["href"] if link_tag else "https://observatoriodefinanzas.com"
            if link.startswith("/"):
                link = "https://observatoriodefinanzas.com" + link
            summary_tag = card.find("p")
            summary = summary_tag.get_text(strip=True)[:280] if summary_tag else ""
            results.append(
                {
                    "title": f"[OVF] {title}",
                    "summary": summary,
                    "link": link,
                    "published": datetime.now().isoformat(),
                    "source": "📊 OVF (Finanzas Venezuela)",
                    "type": "ovf",
                }
            )

        if not results:
            results.append(
                {
                    "title": "OVF: Indicadores económicos Venezuela",
                    "summary": "Visita el Observatorio Venezolano de Finanzas para datos actualizados.",
                    "link": "https://observatoriodefinanzas.com",
                    "published": datetime.now().isoformat(),
                    "source": "📊 OVF",
                    "type": "ovf",
                }
            )
    except Exception as e:
        logger.warning(f"OVF: {e}")
    return results


# ════════════════════════════════════════════════════════════════
# 8. GACETA OFICIAL — Decretos y resoluciones del gobierno
# ════════════════════════════════════════════════════════════════
_gaceta_cb = {"disabled": False}


def get_gaceta_oficial() -> List[Dict[str, Any]]:
    """Scraping de la Gaceta Oficial de Venezuela."""
    results = []
    if _gaceta_cb["disabled"]:
        return results
    urls = [
        "https://www.gacetaoficial.gob.ve",
        "https://gacetaoficial.gob.ve/publico/index.html",
    ]
    for base_url in urls:
        try:
            resp = safe_get(base_url, timeout=10)
            if resp is None or resp.status_code != 200:
                _gaceta_cb["disabled"] = True
                break
            soup = BeautifulSoup(resp.content, "html.parser")
            items = soup.find_all(["li", "tr", "div", "article"], limit=20)
            for item in items:
                text = item.get_text(strip=True)
                if len(text) < 20:
                    continue
                if any(kw in text.lower() for kw in ["decreto", "resolución", "gaceta", "número", "extraordinaria"]):
                    link_tag = item.find("a", href=True)
                    link = link_tag["href"] if link_tag else base_url
                    if link.startswith("/"):
                        link = base_url + link
                    results.append(
                        {
                            "title": f"[Gaceta] {text[:120]}",
                            "summary": "Publicación oficial del gobierno venezolano.",
                            "link": link,
                            "published": datetime.now().isoformat(),
                            "source": "📜 Gaceta Oficial VE",
                            "type": "gaceta",
                        }
                    )
                    if len(results) >= 5:
                        break
            if results:
                break
        except Exception as e:
            logger.warning(f"Gaceta ({base_url}) error: {e}. Desactivando temporalmente.")
            _gaceta_cb["disabled"] = True
            break
    return results


# ════════════════════════════════════════════════════════════════
# 9. VESSELTRACKING — Barcos en puertos venezolanos (scraping público)
# ════════════════════════════════════════════════════════════════
def get_vessel_venezuela() -> List[Dict[str, Any]]:
    """Embarcaciones en aguas venezolanas vía VesselFinder (scraping)."""
    results = []
    try:
        # Puerto La Guaira, Maracaibo, Puerto Ordaz
        ports = {
            "Puerto La Guaira": "https://www.myshiptracking.com/ports/view/slug=la-guaira-port",
            "Puerto Maracaibo": "https://www.myshiptracking.com/ports/view/slug=maracaibo-port",
        }
        port_coords = {
            "Puerto La Guaira": {"lat": 10.6062, "lon": -66.9356},
            "Puerto Maracaibo": {"lat": 10.6667, "lon": -71.6167},
        }
        for port_name, url in ports.items():
            coords = port_coords.get(port_name, {"lat": 10.5, "lon": -66.5})
            resp = safe_get(url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "html.parser")
                ships = soup.find_all("tr", class_=lambda c: c and "vessel" in c.lower())[:10]
                if ships:
                    for s in ships:
                        name = s.get_text(strip=True)[:40] or "Embarcación"
                        results.append(
                            {
                                "title": f"🚢 {name}",
                                "summary": f"Puerto: {port_name} | Monitoreo OSINT",
                                "link": url,
                                "published": datetime.now().isoformat(),
                                "source": "🚢 Vessel Tracker",
                                "type": "vessel",
                                "latitude": coords["lat"],
                                "longitude": coords["lon"],
                            }
                        )
    except Exception as e:
        logger.warning(f"VesselTracker: {e}")

    # Fallback informativo si el scraping no funciona
    if not results:
        results.append(
            {
                "title": "Tráfico marítimo Venezuela: Ver mapa en tiempo real",
                "summary": "Monitorea petroleros PDVSA y buques en puertos venezolanos vía MarineTraffic.",
                "link": "https://www.marinetraffic.com/en/ais/home/centerx:-66/centery:10/zoom:7",
                "published": datetime.now().isoformat(),
                "source": "🚢 Marine Traffic VE",
                "type": "vessel",
                "latitude": 10.5,
                "longitude": -66.5,
            }
        )

    return results


# ════════════════════════════════════════════════════════════════
# INTEGRADOR PRINCIPAL
# ════════════════════════════════════════════════════════════════
def get_realtime_data() -> Dict[str, Any]:
    """Ejecuta todos los módulos de inteligencia en tiempo real."""
    import concurrent.futures

    now = datetime.now().isoformat()
    data = {"timestamp": now, "sources": {}, "count": 0}

    tasks = [
        ("Internet VE (IODA)", get_ioda_outages),
        ("ISPs BGP Venezuela", get_bgpview_ve),
        ("Tipo de Cambio", get_dolar_rates),
        ("Conflicto Armado (ACLED)", get_acled_venezuela),
        ("Vuelos ADS-B", get_adsb_venezuela),
        ("Crisis Humanitaria", get_reliefweb_venezuela),
        ("Ciberseguridad (ExploitDB)", get_exploitdb),
        ("OVF Finanzas", get_ovf_data),
        ("Gaceta Oficial", get_gaceta_oficial),
        ("Trafico Maritimo", get_vessel_venezuela),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fn): name for name, fn in tasks}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                items = future.result()
                if items:
                    data["sources"][name] = items
                    data["count"] += len(items)
                    logger.info(f"{name}: {len(items)} item(s)")
            except Exception as e:
                logger.error(f"{name}: {e}")

    logger.info(f"Total inteligencia en tiempo real: {data['count']} items")
    return data


if __name__ == "__main__":
    print("=== TEST MÓDULO OSINT REALTIME ===")
    d = get_realtime_data()
    print(f"\nTotal: {d['count']} items")
    for src, items in d["sources"].items():
        print(f"  [{len(items):2d}] {src}")
        for i in items[:1]:
            print(f"        -> {i['title'][:70]}")
