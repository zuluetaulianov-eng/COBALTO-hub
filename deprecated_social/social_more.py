# social_more.py - Más fuentes públicas
# Tráfico, terremotos, startups, leyes, y más

from datetime import datetime
from typing import Any, Dict, List

import feedparser

from social_public_extractor import safe_get  # Tor + fallback anti-censura


# ==========================================
# TRÁFICO Y MAPAS - OpenStreetMap / Waze
# ==========================================
def get_traffic_venezuela() -> List[Dict[str, Any]]:
    """Estado del tráfico en Venezuela (vía Traffic Manager)"""
    results = []
    results.append(
        {
            "title": "Tráfico Caracas: Mapas",
            "summary": "Consultar en OpenStreetMap o Waze",
            "link": "https://openstreetmap.org",
            "published": datetime.now().isoformat(),
            "source": "OpenStreetMap",
            "type": "traffic",
        }
    )
    return results


def get_waze_alerts() -> List[Dict[str, Any]]:
    """Alertas de Waze (vía API pública limitada)"""
    results = []
    try:
        # Waze usa API propia, solo informamos
        results.append(
            {
                "title": "Waze Venezuela: Consultar app",
                "summary": "Alertas de tráfico en tiempo real vía app.waze.com",
                "link": "https://www.waze.com/live-map",
                "published": datetime.now().isoformat(),
                "source": "Waze",
                "type": "traffic",
            }
        )
    except Exception as e:
        print(f"[WARN] Waze: {e}")
    return results


# ==========================================
# TERREMOTOS - USGS
# ==========================================
def get_earthquakes() -> List[Dict[str, Any]]:
    """Terremotos recientes (USGS)"""
    results = []
    results.append(
        {
            "title": "Sismicidad: Consultar USGS",
            "summary": "Ver actividad sísmica en earthquake.usgs.gov",
            "link": "https://earthquake.usgs.gov",
            "published": datetime.now().isoformat(),
            "source": "USGS",
            "type": "earthquake",
        }
    )
    return results


def get_earthquakes_region() -> List[Dict[str, Any]]:
    """Terremotos región Caribbean"""
    results = []
    try:
        results.append(
            {
                "title": "Caribe: Sismicidad activa",
                "summary": "Consultar actividad sísmica en region.caribbean@usgs.gov",
                "link": "https://earthquake.usgs.gov",
                "published": datetime.now().isoformat(),
                "source": "USGS Caribbean",
                "type": "earthquake",
            }
        )
    except Exception as e:
        print(f"[WARN] Caribe: {e}")
    return results


# ==========================================
# STARTUPS Y CROWDFUNDING
# ==========================================
def get_kickstarter_venezuela() -> List[Dict[str, Any]]:
    """Proyectos de Kickstarter con tema Venezuela"""
    results = []
    results.append(
        {
            "title": "Kickstarter: Explorar proyectos Venezuela",
            "summary": "Buscar proyectos en kickstarter.com",
            "link": "https://www.kickstarter.com/discover/search?term=venezuela",
            "published": datetime.now().isoformat(),
            "source": "Kickstarter",
            "type": "startup",
        }
    )
    return results


def get_producthunt() -> List[Dict[str, Any]]:
    """Productos trending en Product Hunt"""
    results = []
    try:
        # Solo información
        results.append(
            {
                "title": "Product Hunt: Explorar",
                "summary": "Productos nuevos y trending en producthunt.com",
                "link": "https://www.producthunt.com",
                "published": datetime.now().isoformat(),
                "source": "Product Hunt",
                "type": "startup",
            }
        )
    except Exception as e:
        print(f"[WARN] Product Hunt: {e}")
    return results


# ==========================================
# LEYES, DECRETOS Y GACETA OFICIAL
# ==========================================
def get_gaceta_oficial() -> List[Dict[str, Any]]:
    """Gaceta Oficial de Venezuela"""
    results = []
    try:
        # TSJ - Gaceta
        results.append(
            {
                "title": "Gaceta Oficial: Consultar",
                "summary": "Últimos decretos y leyes en gacetaoficial.gob.ve",
                "link": "https://www.gacetaoficial.gob.ve",
                "published": datetime.now().isoformat(),
                "source": "Gaceta Oficial",
                "type": "law",
            }
        )
    except Exception as e:
        print(f"[WARN] Gaceta: {e}")
    return results


def get_asenac() -> List[Dict[str, Any]]:
    """Noticias de la Asamblea Nacional"""
    results = []
    results.append(
        {
            "title": "Asamblea Nacional: Últimas noticias",
            "summary": "Consultar en asemblea.gob.ve",
            "link": "https://www.asemblea.gob.ve",
            "published": datetime.now().isoformat(),
            "source": "Asistencia Nacional",
            "type": "law",
        }
    )
    return results


# ==========================================
# EDUCACIÓN Y UNIVERSIDADES
# ==========================================
def get_universities() -> List[Dict[str, Any]]:
    """Noticias de universidades venezolanas"""
    results = []
    univs = ["UCV", "USB", "ULA", "UNEXPO", "UC"]
    for univ in univs:
        results.append(
            {
                "title": f"Universidad {univ}: Noticias",
                "summary": f"Consultar sitio oficial de U{univ}",
                "link": "https://www.google.com/search?q=universidad+venezuela+noticias",
                "published": datetime.now().isoformat(),
                "source": f"Universidad {univ}",
                "type": "education",
            }
        )
    return results


# ==========================================
# DEPORTES
# ==========================================
def get_sports_venezuela() -> List[Dict[str, Any]]:
    """Deportes en Venezuela"""
    sources = {
        "FVF (Futbol)": "https://www.fvf.com.ve/feed/",
        "LVBP": "https://lvbp.com/feed/",
    }

    results = []
    for name, url in sources.items():
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:2]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "sports",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# TURISMO Y CULTURA
# ==========================================
def get_tourism() -> List[Dict[str, Any]]:
    """Turismo y cultura Venezuela"""
    results = []

    # Mintur
    try:
        resp = safe_get("https://www.mintur.gob.ve/feed/")
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:3]:
            results.append(
                {
                    "title": entry.get("title", "Sin título")[:140],
                    "summary": entry.get("summary", "")[:280],
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", ""),
                    "source": "Ministerio Turismo",
                    "type": "tourism",
                }
            )
    except Exception as e:
        print(f"[WARN] Mintur: {e}")

    # UNESCO
    try:
        resp = safe_get("https://whc.unesco.org/en/rss/100/")
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:2]:
            if "Venezuela" in entry.get("title", ""):
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": "UNESCO Venezuela",
                        "type": "tourism",
                    }
                )
    except Exception as e:
        print(f"[WARN] UNESCO: {e}")

    return results


# ==========================================
# MEDIO AMBIENTE
# ==========================================
def get_environment() -> List[Dict[str, Any]]:
    """Noticias ambientales"""
    sources = {
        "Greenpeace": "https://www.greenpeace.org/feed/",
        "PNUMA": "https://www.unep.org/rss",
        "Ambientum": "https://www.ambientum.com/feed/",
    }

    results = []
    for name, url in sources.items():
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:2]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "environment",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# CIENCIA Y ESPACIO
# ==========================================
def get_space_news() -> List[Dict[str, Any]]:
    """Noticias de ciencia y espacio"""
    sources = {
        "NASA": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "ESA": "https://www.esa.int/rss",
        "Space.com": "https://www.space.com/feeds/rss/all",
    }

    results = []
    for name, url in sources.items():
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:2]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "science",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# RADIO Y STREAMING
# ==========================================
def get_radio_stations() -> List[Dict[str, Any]]:
    """Radios y streaming Venezuela"""
    results = []

    stations = [
        ("Radio Nacional de Venezuela", "https://www.rnv.gob.ve/feed/"),
        ("Radio Caracas", "https://radiocaracas.com/feed/"),
        ("Globovisión", "https://globovision.com/feed/"),
    ]

    for name, url in stations:
        try:
            resp = safe_get(url)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:2]:
                results.append(
                    {
                        "title": entry.get("title", "Sin título")[:140],
                        "summary": entry.get("summary", "")[:280],
                        "link": entry.get("link", "#"),
                        "published": entry.get("published", ""),
                        "source": name,
                        "type": "radio",
                    }
                )
        except Exception as e:
            print(f"[WARN] {name}: {e}")
    return results


# ==========================================
# UNIFICAR
# ==========================================
def get_more_sources() -> Dict[str, Any]:
    """Recolecta todas las fuentes adicionales"""
    import concurrent.futures

    now = datetime.now().isoformat()
    data = {"timestamp": now, "sources": {}, "count": 0}

    sources_funcs = [
        ("Tráfico/Mapas", get_traffic_venezuela),
        ("Terremotos", get_earthquakes),
        ("Startups/Crowdfunding", get_kickstarter_venezuela),
        ("Gaceta/Leyes", get_gaceta_oficial),
        ("Asamblea Nacional", get_asenac),
        ("Universidades", get_universities),
        ("Deportes Venezuela", get_sports_venezuela),
        ("Turismo/Cultura", get_tourism),
        ("Medio Ambiente", get_environment),
        ("Ciencia/Espacio", get_space_news),
        ("Radio/Streaming", get_radio_stations),
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
    print("=== Más fuentes SIN credenciales ===")
    data = get_more_sources()
    print(f"Total: {data['count']} items")
    for source, items in data["sources"].items():
        print(f"  {source}: {len(items)} items")
