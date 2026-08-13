"""
COBALTO HUB - GitHub Intelligence Module
Rastreador de fugas de datos (Data Leaks), PoCs, exploits y repositorios OSINT
"""
import logging
import os
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

def get_github_intel() -> dict:
    """
    Busca en GitHub repositorios y códigos recientes (leaks, exploits).
    Soporta fallback dinámico (con o sin GITHUB_TOKEN).
    """
    results = {
        "sources": {"GitHub Threat Intel": []},
        "count": 0,
        "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S")
    }

    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    # Consultas tácticas
    queries = [
        "venezuela leak",
        "venezuela osint",
        "pdvsa exploit",
        "cantv dump",
        "botnet vzla",
        "0day exploit"
    ]

    entries = []

    try:
        # Búsqueda prioritaria de repositorios por tema (Threat Intel y OSINT)
        # Esto sirve para encontrar herramientas y recursos nuevos
        topic_url = "https://api.github.com/search/repositories?q=topic:threat-intelligence+topic:osint+created:>2025-01-01&sort=updated&order=desc&per_page=3"
        resp_topic = requests.get(topic_url, headers=headers, timeout=10)
        if resp_topic.status_code == 200:
            for item in resp_topic.json().get("items", []):
                entries.append({
                    "title": f"🛠️ [HERRAMIENTA OSINT] {item.get('full_name')}",
                    "link": item.get('html_url'),
                    "summary": item.get('description', 'Sin descripción')[:200],
                    "published": item.get('updated_at', ''),
                    "source": "GitHub Intelligence",
                    "type": "ciberseguridad"
                })
        if not token:
            time.sleep(2)  # Respetar rate limit anónimo

        # Búsquedas por palabras clave
        for q in queries[:4]: # Limitamos a 4 para no gastar cuota anónima rápido
            url = f"https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page=2"
            resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", []):
                    entries.append({
                        "title": f"⚠️ [REPORTE INTEL] {item.get('full_name')}",
                        "link": item.get('html_url'),
                        "summary": item.get('description', 'Posible filtración o código sospechoso detectado.')[:200],
                        "published": item.get('updated_at', ''),
                        "source": "GitHub Intelligence",
                        "type": "alerta_temprana"
                    })
            elif resp.status_code == 403:
                logger.warning("[GITHUB] Rate Limit excedido. Operando en modo degrado.")
                break # Romper si el límite se agotó

            if not token:
                time.sleep(2)

    except Exception as e:
        logger.debug(f"[GITHUB OSINT] Error en búsqueda táctica: {e}")

    # Deduplicar por link
    unique_entries = {e["link"]: e for e in entries}.values()

    results["sources"]["GitHub Threat Intel"] = list(unique_entries)
    results["count"] = len(unique_entries)

    if results["count"] > 0:
        logger.info(f"[GITHUB OSINT] Recolectados {results['count']} repositorios de inteligencia.")

    return results
