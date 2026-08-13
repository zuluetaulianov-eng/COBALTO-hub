# osint_onion.py - Módulo 2: Monitoreo de fuentes .onion via Tor
# Accede a medios internacionales censurados vía red Tor

import socket
from datetime import datetime
from typing import Any, Dict, List

import feedparser
import requests
import urllib3

urllib3.disable_warnings()

# ============================================================
# FUENTES .ONION — Medios internacionales con versión Tor
# ============================================================
ONION_NEWS_SOURCES = {
    "New York Times (Onion)": "https://nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljsciiyd.onion/",
    "Deutsche Welle (Onion)": "https://dwnewsvdyyiamwnp.onion/es/",
    "ProPublica (Onion)": "https://p53lf57qovyuvwsc6xnrppyply3vtqm7l6pcobkmyqg2ad9p6ts/rss",
    "BBC Onion": "https://www.bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion/mundo/rss.xml",
}

# Directorio de onions activos (clearnet)
ONION_DIRECTORIES = {
    "Dark.fail": "https://dark.fail/",
}


def _detect_tor_port() -> int:
    """Detecta el puerto de Tor disponible (9150, 9050, 9151)"""
    for port in [9150, 9050, 9151]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            try:
                result = sock.connect_ex(("127.0.0.1", port))
                if result == 0:
                    print(f"[ONION] Tor detectado en puerto {port}")
                    return port
            finally:
                sock.close()
        except Exception:
            continue
    print("[ONION] Tor no disponible en puertos 9150, 9050, 9151")
    return None


def _onion_get(url: str):
    """Petición forzada SOLO via Tor. Las .onion no funcionan sin Tor."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}

    # Detectar puerto de Tor disponible
    tor_port = _detect_tor_port()
    if not tor_port:
        raise Exception("Tor no disponible - las conexiones .onion requieren Tor")

    tor_proxies = {"http": f"socks5h://127.0.0.1:{tor_port}", "https": f"socks5h://127.0.0.1:{tor_port}"}

    return requests.get(url, headers=headers, proxies=tor_proxies, timeout=30)


def get_onion_news() -> List[Dict[str, Any]]:
    """Extrae noticias de fuentes .onion via Tor."""
    results = []
    for name, url in ONION_NEWS_SOURCES.items():
        try:
            resp = _onion_get(url)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:4]:
                    results.append(
                        {
                            "title": entry.get("title", "Sin título")[:140],
                            "summary": entry.get("summary", "")[:280],
                            "link": entry.get("link", url),
                            "published": entry.get("published", datetime.now().isoformat()),
                            "source": f"🧅 {name}",
                            "type": "onion",
                        }
                    )
                if feed.entries:
                    print(f"[ONION] {name}: {len(feed.entries)} entradas via Tor")
        except Exception as e:
            # Silenciar errores de conexión Onion comunes - no spam en logs
            err_str = str(e)
            if "SOCKS" in err_str or "Unknown error" in err_str or "Host unreachable" in err_str:
                # Error de conexión Onion común - no imprimir
                pass
            else:
                print(f"[ONION-WARN] {name}: {e}")
    return results


def get_onion_data() -> Dict[str, Any]:
    """Punto de entrada principal para el módulo Onion."""
    now = datetime.now().isoformat()
    items = get_onion_news()
    data = {"timestamp": now, "sources": {}, "count": 0, "tor_active": True}

    tor_port = _detect_tor_port()
    if not tor_port:
        data["tor_active"] = False
        print("[ONION] Tor no detectado. Enlace .onion desactivado.")
        return data

    if items:
        data["sources"]["Darknet (Onion via Tor)"] = items
        data["count"] = len(items)
        print(f"[ONION] Total: {data['count']} artículos via red Tor")
    else:
        print("[ONION] Sin datos (¿Tor Browser abierto?)")
    return data


if __name__ == "__main__":
    print("=== TEST MÓDULO ONION ===")
    d = get_onion_data()
    print(f"Total: {d['count']} items")
    for src, items in d["sources"].items():
        print(f"  {src}: {len(items)} items")
        for i in items[:2]:
            print(f"    - {i['title']}")
