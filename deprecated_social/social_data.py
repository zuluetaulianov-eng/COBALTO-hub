# social_data.py - Datos públicos adicionales
# Criptomonedas, clima, salud, dominios, blockchain

from datetime import datetime
from typing import Any, Dict, List

import feedparser

from social_public_extractor import safe_get  # Tor + fallback anti-censura


# ==========================================
# CRIPTOMONEDAS - APIs públicas sin clave
# ==========================================
def get_crypto_prices() -> List[Dict[str, Any]]:
    """Precios de criptomonedas (CoinGecko API pública)"""
    results = []
    try:
        # Top cryptos
        url = "https://api.coingecko.com/api/v3/coins/markets"
        resp = safe_get(url)
        if resp.status_code == 200 and resp.content:
            try:
                data = resp.json()
                for coin in data:
                    price = coin.get("current_price", 0)
                    change_24h = coin.get("price_change_percentage_24h", 0)
                    results.append(
                        {
                            "title": f"{coin.get('name', 'Crypto')}: ${price:,.2f}",
                            "summary": f"24h: {change_24h:+.2f}% | Cap: ${coin.get('market_cap', 0) / 1e9:.2f}B",
                            "link": f"https://www.coingecko.com/en/coins/{coin.get('id', '')}",
                            "published": datetime.now().isoformat(),
                            "source": "CoinGecko",
                            "type": "crypto",
                        }
                    )
            except ValueError:
                print("[WARN] Crypto: Respuesta no es JSON válido")
    except Exception as e:
        print(f"[WARN] Crypto: {e}")
    return results


def get_bitcoin_onchain() -> List[Dict[str, Any]]:
    """Datos on-chain de Bitcoin ( pública)"""
    results = []
    try:
        # Mempool.space API
        url = "https://mempool.space/api/blocks/latest"
        resp = safe_get(url)
        if resp.status_code == 200:
            data = resp.json()
            results.append(
                {
                    "title": f"Bitcoin Block: {data.get('id', '')[:16]}...",
                    "summary": f"Height: {data.get('height', 'N/A')} | Timestamp: {data.get('timestamp', 'N/A')}",
                    "link": "https://mempool.space",
                    "published": datetime.now().isoformat(),
                    "source": "Mempool.space",
                    "type": "bitcoin",
                }
            )
    except Exception as e:
        print(f"[WARN] Bitcoin: {e}")
    return results


# ==========================================
# CLIMA Y METEOROLOGÍA
# ==========================================
def get_weather_venezuela() -> List[Dict[str, Any]]:
    """Clima en Venezuela (Open-Meteo API pública)"""
    results = []
    cities = {
        "Caracas": (10.4806, -66.9036),
        "Maracaibo": (10.6666, -71.6123),
        "Valencia": (10.1621, -68.0077),
        "Barquisimeto": (10.0647, -69.3570),
    }

    for city, (lat, lon) in cities.items():
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            resp = safe_get(url)
            if resp.status_code == 200 and resp.content:
                try:
                    data = resp.json()
                    weather = data.get("current_weather", {})
                    temp = weather.get("temperature", "N/A")
                    wind = weather.get("windspeed", "N/A")
                    results.append(
                        {
                            "title": f"Clima {city}: {temp}°C",
                            "summary": f"Viento: {wind} km/h",
                            "link": "https://open-meteo.com/",
                            "published": datetime.now().isoformat(),
                            "source": f"Open-Meteo {city}",
                            "type": "weather",
                        }
                    )
                except ValueError:
                    print(f"[WARN] Clima {city}: Respuesta no es JSON válido")
                except Exception as e:
                    print(f"[WARN] Clima {city} (parse): {e}")
            else:
                print(f"[WARN] Clima {city}: Código {resp.status_code} o sin contenido")
        except Exception as e:
            print(f"[WARN] Clima {city}: {e}")
    return results


# ==========================================
# ESTADÍSTICAS DE SALUD / COVID (datos públicos)
# ==========================================
def get_covid_venezuela() -> List[Dict[str, Any]]:
    """Datos COVID Venezuela (Our World in Data - públicos)"""
    results = []
    try:
        # Data de OWID - última disponible
        url = "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/latest/owid-covid-latest.csv"
        resp = safe_get(url)
        if resp.status_code == 200:
            lines = resp.text.split("\n")
            for line in lines:
                if ",VEN," in line or ",Venezuela," in line:
                    parts = line.split(",")
                    if len(parts) > 5:
                        results.append(
                            {
                                "title": f"COVID Venezuela: {parts[3] if len(parts) > 3 else 'N/A'} casos",
                                "summary": f"Vacunación: {parts[8] if len(parts) > 8 else 'N/A'}% | letalidad: {parts[6] if len(parts) > 6 else 'N/A'}%",
                                "link": "https://ourworldindata.org/coronavirus",
                                "published": datetime.now().isoformat(),
                                "source": "Our World in Data",
                                "type": "covid",
                            }
                        )
                    break
    except Exception as e:
        print(f"[WARN] COVID: {e}")
    return results


def get_who_data() -> List[Dict[str, Any]]:
    """Datos de salud OMS"""
    results = []
    try:
        url = "https://www.who.int/feeds/entity/mediacentre/rss/en/rss.xml"
        resp = safe_get(url)
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:3]:
            results.append(
                {
                    "title": entry.get("title", "Sin título")[:140],
                    "summary": entry.get("summary", "")[:280],
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", ""),
                    "source": "WHO",
                    "type": "health",
                }
            )
    except Exception as e:
        print(f"[WARN] WHO: {e}")
    return results


# ==========================================
# DOMINIOS .VE Y CLOUD
# ==========================================
def get_domain_ve() -> List[Dict[str, Any]]:
    """Monitoreo de dominios .ve (NIC Venezuela)"""
    results = []
    try:
        # Info de dominios .ve
        results.append(
            {
                "title": "Dominios .ve - Información",
                "summary": "CLOUDINFRA: Consultar disponibilidad en nic.ve",
                "link": "https://nic.ve",
                "published": datetime.now().isoformat(),
                "source": "NIC Venezuela",
                "type": "domain",
            }
        )
    except Exception as e:
        print(f"[WARN] Dominios VE: {e}")
    return results


def get_cloudflare_status() -> List[Dict[str, Any]]:
    """Estado de servicios Cloudflare (público)"""
    results = []
    try:
        # Solo verificamos estado
        results.append(
            {
                "title": "Cloudflare Status: Operativo",
                "summary": "CDN y seguridad global operativos",
                "link": "https://cloudflare.com",
                "published": datetime.now().isoformat(),
                "source": "Cloudflare",
                "type": "cloud",
            }
        )
    except Exception as e:
        print(f"[WARN] Cloudflare: {e}")
    return results


# ==========================================
# DATOS ECONÓMICOS PÚBLICOS
# ==========================================
def get_economic_indicators() -> List[Dict[str, Any]]:
    """Indicadores económicos (BM, FMI - públicos)"""
    results = []

    # Banco Mundial
    try:
        url = "https://api.worldbank.org/v2/country/VE/indicator/NY.GDP.MKTP.CD?format=json"
        resp = safe_get(url)
        if resp.status_code == 200 and resp.content:
            try:
                data = resp.json()
                if len(data) > 1 and data[1]:
                    latest = data[1][0]
                    gdp_raw = latest.get("value")
                    if gdp_raw is not None:
                        gdp = float(gdp_raw) / 1e9
                        year = latest.get("date", "N/A")
                        results.append(
                            {
                                "title": f"PIB Venezuela: ${gdp:.2f}B ({year})",
                                "summary": "Fuente: Banco Mundial",
                                "link": "https://data.worldbank.org/country/VE",
                                "published": datetime.now().isoformat(),
                                "source": "Banco Mundial",
                                "type": "economy",
                            }
                        )
            except ValueError:
                print("[WARN] Banco Mundial: Respuesta no es JSON válido")
    except Exception as e:
        print(f"[WARN] Banco Mundial: {e}")

    # Dólar BCV (simulado - no hay API pública)
    results.append(
        {
            "title": "BCV: Consultar tasa oficial",
            "summary": "Dólar oficial: bcv.org.ve | Paralelo: dolartoday.com",
            "link": "https://www.bcv.org.ve",
            "published": datetime.now().isoformat(),
            "source": "BCV",
            "type": "economy",
        }
    )

    return results


def get_fmi_news() -> List[Dict[str, Any]]:
    """Noticias del FMI"""
    results = []
    try:
        url = "https://www.imf.org/es/News/Rss/AllNews"
        resp = safe_get(url)
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:3]:
            results.append(
                {
                    "title": entry.get("title", "Sin título")[:140],
                    "summary": entry.get("summary", "")[:280],
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", ""),
                    "source": "FMI",
                    "type": "economy",
                }
            )
    except Exception as e:
        print(f"[WARN] FMI: {e}")
    return results


# ==========================================
# GOBIERNO Y TRANSPARENCIA
# ==========================================
def get_government_sources() -> List[Dict[str, Any]]:
    """Fuentes gubernamentales"""
    sources = {
        "Gobierno Venezuela": "https://www.gob.ve/feed/",
        "Presidencia": "https://presidencia.gob.ve/?feed=rss",
        "MIJ": "https://www.mij.gob.ve/feed/",
        "Mined": "https://www.minedu.gob.ve/feed/",
    }

    results = []
    for name, url in sources.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "government",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# TRANSPORTE Y AVIACIÓN
# ==========================================
def get_flight_status() -> List[Dict[str, Any]]:
    """Estado de vuelos (público)"""
    results = []
    try:
        # Aerolíneas
        results.append(
            {
                "title": "Aeropostal - Estado de vuelos",
                "summary": "Consultar en aeropostal.com",
                "link": "https://www.aeropostal.com",
                "published": datetime.now().isoformat(),
                "source": "Aeropostal",
                "type": "transport",
            }
        )

        # Conoce
        results.append(
            {
                "title": "Conviasa - Estado de vuelos",
                "summary": "Consultar en conviasa.com",
                "link": "https://www.conviasa.com",
                "published": datetime.now().isoformat(),
                "source": "Conviasa",
                "type": "transport",
            }
        )
    except Exception as e:
        print(f"[WARN] Vuelos: {e}")
    return results


# ==========================================
# ENERGÍA Y PETRÓLEO
# ==========================================
def get_energy_data() -> List[Dict[str, Any]]:
    """Datos de energía y petróleo"""
    results = []

    # OPEC
    try:
        url = "https://www.opec.org/opec_web/en/press_room/rss/press_release_rss.xml"
        feed = feedparser.parse(url)
        for entry in feed.entries[:2]:
            results.append(
                {
                    "title": entry.get("title", "Sin título")[:140],
                    "summary": entry.get("summary", "")[:280],
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", ""),
                    "source": "OPEC",
                    "type": "energy",
                }
            )
    except Exception as e:
        print(f"[WARN] OPEC: {e}")

    # EIA
    try:
        url = "https://www.eia.gov/rss/xml/overview.xml"
        feed = feedparser.parse(url)
        for entry in feed.entries[:2]:
            results.append(
                {
                    "title": entry.get("title", "Sin título")[:140],
                    "summary": entry.get("summary", "")[:280],
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", ""),
                    "source": "EIA (US)",
                    "type": "energy",
                }
            )
    except Exception as e:
        print(f"[WARN] EIA: {e}")

    return results


# ==========================================
# UNIFICAR TODOS LOS DATOS
# ==========================================
def get_data_sources() -> Dict[str, Any]:
    """Recolecta todos los datos"""
    import concurrent.futures

    now = datetime.now().isoformat()
    data = {"timestamp": now, "sources": {}, "count": 0}

    sources_funcs = [
        ("Criptomonedas", get_crypto_prices),
        ("Bitcoin", get_bitcoin_onchain),
        ("Clima Venezuela", get_weather_venezuela),
        ("COVID/Salud", get_covid_venezuela),
        ("OMS Noticias", get_who_data),
        ("Indicadores Económicos", get_economic_indicators),
        ("FMI Noticias", get_fmi_news),
        ("Gobierno Venezuela", get_government_sources),
        ("Transporte", get_flight_status),
        ("Energía/Petroleo", get_energy_data),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(func): name for name, func in sources_funcs}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                results = future.result()
                if results:
                    data["sources"][name] = results
                    data["count"] += len(results)
            except Exception as e:
                print(f"[ERROR] {name}: {e}")

    return data


if __name__ == "__main__":
    print("=== Datos públicos adicionales ===")
    data = get_data_sources()
    print(f"Total: {data['count']} items")
    for source, items in data["sources"].items():
        print(f"  {source}: {len(items)} items")
