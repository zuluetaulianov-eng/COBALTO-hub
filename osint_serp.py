# osint_serp.py - Módulo 4: Búsqueda SERP activa en Google News + Bing
# Sin API key. Usa RSS públicos de Google News y Bing News.

from datetime import datetime
from typing import Any, Dict, List

import feedparser
import urllib3

from social_public_extractor import safe_get

urllib3.disable_warnings()

# ============================================================
# QUERIES DE BÚSQUEDA ACTIVA — Venezuela foco táctico
# ============================================================
SERP_QUERIES = {
    # ── LEGAL / GUBERNAMENTAL ──────────────────────────────────────
    "Decretos y Resoluciones": 'Venezuela ("Gaceta Oficial" OR "Decreto Presidencial" OR "Providencia Administrativa" OR "Resolucion")',
    "Expropiaciones e Intervenciones": 'Venezuela ("Expropiacion" OR "Intervencion" OR "Licitacion" OR "Adjudicacion directa")',
    "Contratos y Presupuesto": 'Venezuela ("Presupuesto aprobado" OR "Contrato estatal" OR "Asignacion de recursos")',
    # ── ECONOMÍA / FINANZAS ────────────────────────────────────────
    "Indicadores Economicos": 'Venezuela ("Tasa de cambio" OR "Inflacion interanual" OR "Canasta basica" OR "Deficit fiscal")',
    "Reservas y Liquidez": 'Venezuela ("Reserva internacional" OR "Liquidez monetaria" OR "BCV" OR "PDVSA")',
    # ── INFRAESTRUCTURA / SERVICIOS ───────────────────────────────
    "Crisis Electrica": 'Venezuela ("Apagon nacional" OR "Racionamiento electrico" OR "Suministro electrico" OR "Subestacion")',
    "Telecomunicaciones": 'Venezuela ("Caida de red" OR "Corte de fibra optica" OR "Falla de borde" OR "internet")',
    # ── LOGÍSTICA / ABASTECIMIENTO ────────────────────────────────
    "Desabastecimiento": 'Venezuela ("Desabastecimiento" OR "Escasez de combustible" OR "Paralización de transporte")',
    "Puertos y Carga": 'Venezuela ("Puerto cerrado" OR "Desvio de carga" OR "maritimo" OR "contenedores")',
    # ── SANCIONES INTERNACIONALES ─────────────────────────────────
    "Sanciones OFAC": '"Venezuela" ("Sanciones OFAC" OR "Embargo comercial" OR "Congelacion de activos" OR "Lista negra")',
    "Evasion de Sanciones": '"Venezuela" ("Evasion de sanciones" OR "criptomonedas" OR "petroleo" OR "buque sombra")',
    # ── MILITAR / SEGURIDAD NACIONAL ──────────────────────────────
    "Operaciones Militares": 'Venezuela ("Movilizacion militar" OR "FANB" OR "ejercicio militar" OR "zona de seguridad")',
    "Espacio Aereo y Maritimo": 'Venezuela ("Restriccion de espacio aereo" OR "NOTAM" OR "Trafico maritimo anomalo" OR "Cierre de fronteras")',
    "Diplomacia de Emergencia": 'Venezuela ("Evacuacion diplomatica" OR "embajada" OR "consul" OR "cancilleria")',
    # ── CIBERSEGURIDAD / OSINT ────────────────────────────────────
    "Vulnerabilidades Criticas": f'("0-day" OR "Vulnerabilidad critica" OR "CVE-{datetime.now().year}" OR "Data breach") Venezuela',
    "Ataques Ciberneticos": '("Ransomware" OR "Ataque DDoS" OR "Exfiltracion" OR "Leak") Venezuela',
    "Filtraciones de Datos": '("Database dump" OR "Credenciales expuestas" OR "Admin access" OR "Shell upload") Venezuela',
}


def _gnews_url(query: str) -> str:
    """Construye URL de Google News RSS para una búsqueda."""
    q = query.replace(" ", "+")
    return f"https://news.google.com/rss/search?q={q}&hl=es-419&gl=VE&ceid=VE:es"


def _bing_url(query: str) -> str:
    """Construye URL de Bing News RSS para una búsqueda."""
    q = query.replace(" ", "+")
    return f"https://www.bing.com/news/search?q={q}&format=rss&mkt=es-VE"


def search_google_news(label: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Busca en Google News vía RSS."""
    results = []
    try:
        url = _gnews_url(query)
        resp = safe_get(url)
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:limit]:
            results.append(
                {
                    "title": entry.get("title", "Sin título")[:140],
                    "summary": entry.get("summary", "")[:280],
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", datetime.now().isoformat()),
                    "source": f"🔍 GNews: {label}",
                    "type": "serp_google",
                }
            )
    except Exception as e:
        print(f"[SERP-WARN] Google '{label}': {e}")
    return results


def search_bing_news(label: str, query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Busca en Bing News vía RSS."""
    results = []
    try:
        url = _bing_url(query)
        resp = safe_get(url)
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:limit]:
            results.append(
                {
                    "title": entry.get("title", "Sin título")[:140],
                    "summary": entry.get("summary", "")[:280],
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", datetime.now().isoformat()),
                    "source": f"🔍 Bing: {label}",
                    "type": "serp_bing",
                }
            )
    except Exception as e:
        print(f"[SERP-WARN] Bing '{label}': {e}")
    return results


def get_serp_data() -> Dict[str, Any]:
    """Ejecuta todas las búsquedas SERP en paralelo."""
    import concurrent.futures

    now = datetime.now().isoformat()
    data = {"timestamp": now, "sources": {}, "count": 0}
    all_results = []

    def run_search(label, query):
        items = search_google_news(label, query)
        if not items:
            items = search_bing_news(label, query)  # fallback a Bing
        return label, items

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(run_search, lbl, qry): lbl for lbl, qry in SERP_QUERIES.items()}
        for future in concurrent.futures.as_completed(futures):
            try:
                label, items = future.result()
                if items:
                    data["sources"][f"SERP: {label}"] = items
                    data["count"] += len(items)
                    all_results.extend(items)
            except Exception as e:
                print(f"[SERP-ERR] {e}")

    print(f"[SERP] Total búsquedas activas: {data['count']} resultados")

    # Deduplicar resultados cross-source por URL (evita duplicados Google/Bing)
    seen_urls: set = set()
    for key in list(data["sources"].keys()):
        fresh = []
        for item in data["sources"][key]:
            uid = item.get("link") or item.get("title", "")
            if uid and uid not in seen_urls:
                seen_urls.add(uid)
                fresh.append(item)
        if fresh:
            data["sources"][key] = fresh
        else:
            del data["sources"][key]
    data["count"] = sum(len(v) for v in data["sources"].values())

    return data


if __name__ == "__main__":
    print("=== TEST MÓDULO SERP ===")
    d = get_serp_data()
    print(f"Total: {d['count']} items")
    for src, items in list(d["sources"].items())[:3]:
        print(f"  {src}: {len(items)} items")
        for i in items[:2]:
            print(f"    - {i['title']}")
