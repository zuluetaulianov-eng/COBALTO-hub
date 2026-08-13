# osint_network_resilience.py - Monitoreo de Resiliencia de Red y Apagones v1.0
# Monitorea la conectividad regional (latencias, timeouts de gateways clave)
# y analiza pasivamente las noticias y redes cargadas para detectar reportes de apagones.

import concurrent.futures
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

import requests
import urllib3

from dashboard_state import state

# Desactivar advertencias de certificados auto-firmados en hosts estatales
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Configuración de Monitoreo de Infraestructura
MONITORED_HOSTS = [
    {"name": "🇻🇪 CANTV (Troncal Telecom)", "url": "https://www.cantv.com.ve", "critical": True},
    {"name": "🇻🇪 Plataforma Patria (Servicios Sociales)", "url": "https://www.patria.org.ve", "critical": True},
    {"name": "🇻🇪 Banco Central de Vzla (BCV)", "url": "https://www.bcv.org.ve", "critical": False},
    {"name": "🇻🇪 CNE Electoral", "url": "http://www.cne.gob.ve", "critical": False},
    {"name": "🌐 Enlace DNS Primario (Cloudflare DoH)", "url": "https://cloudflare-dns.com/dns-query", "critical": False},
]

# Palabras clave para la detección pasiva de apagones y fallas eléctricas
BLACKOUT_KEYWORDS = [
    "sin luz", "apagón", "apagon", "apagones", "sin electricidad",
    "falla electrica", "falla eléctrica", "corte electrico", "corte eléctrico",
    "cortes de luz", "racionamiento electrico", "racionamiento eléctrico",
    "corpoelec", "cantv caido", "caida de internet", "caída de internet",
    "sin internet", "cantv caído"
]

def check_host_connectivity(host: Dict[str, Any]) -> Dict[str, Any]:
    """Prueba la conectividad y mide la latencia de un host específico."""
    result = {
        "name": host["name"],
        "url": host["url"],
        "critical": host["critical"],
        "online": False,
        "latency_ms": 9999,
        "error": None
    }

    start_time = time.time()
    try:
        # Petición HTTP ligera con cabecera de agente común
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CobaltoHub/9.5 NetworkMonitor"}
        resp = requests.get(host["url"], headers=headers, timeout=2.5, verify=False)
        result["latency_ms"] = int((time.time() - start_time) * 1000)

        # Consideramos online si responde cualquier código HTTP (incluso errores 403, 500, etc., ya que indica enrutamiento activo)
        result["online"] = True
        result["status_code"] = resp.status_code
    except requests.exceptions.Timeout:
        result["error"] = "TIMEOUT"
    except requests.exceptions.ConnectionError:
        result["error"] = "CONEXION_RECHAZADA"
    except Exception as e:
        result["error"] = str(e)[:30]

    return result

def get_blackout_keyword_reports() -> Dict[str, Any]:
    """Analiza pasivamente la caché global de noticias para contar reportes de apagones."""
    total_entries = state.last_entries_cache or []
    count = 0
    relevant_items = []

    for item in total_entries:
        title = item.get("title", "").lower()
        summary = item.get("summary", "").lower()
        text = title + " " + summary

        # Buscar palabras clave
        found_kws = [kw for kw in BLACKOUT_KEYWORDS if kw in text]
        if found_kws:
            count += 1
            if len(relevant_items) < 5:  # Limitar a los 5 más recientes para la alerta
                relevant_items.append({
                    "title": item.get("title", ""),
                    "source": item.get("source", "Radar Social"),
                    "published": item.get("published", ""),
                    "keywords": found_kws
                })

    return {
        "count": count,
        "examples": relevant_items
    }

def get_network_resilience_alerts() -> List[Dict[str, Any]]:
    """Ejecuta los tests y el análisis para retornar alertas e indicadores de resiliencia."""
    alerts = []

    # 1. Ejecutar pruebas de conectividad de forma concurrente
    checked_hosts = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(check_host_connectivity, host): host for host in MONITORED_HOSTS}
        for future in concurrent.futures.as_completed(futures):
            try:
                checked_hosts.append(future.result())
            except Exception as e:
                logger.warning(f"Error ejecutando test de red: {e}")

    # 2. Analizar reportes sociales
    blackout_data = get_blackout_keyword_reports()
    blackout_count = blackout_data["count"]

    # 3. Calcular Índice de Resiliencia de Red y Eléctrica (0% a 100%)
    resilience_score = 100
    critical_offline = 0
    general_offline = 0
    total_latency = 0
    active_hosts_count = 0

    for h in checked_hosts:
        if not h["online"]:
            if h["critical"]:
                resilience_score -= 20
                critical_offline += 1
            else:
                resilience_score -= 10
                general_offline += 1
        else:
            active_hosts_count += 1
            total_latency += h["latency_ms"]
            # Penalización por latencia crítica (> 500ms)
            if h["latency_ms"] > 800:
                resilience_score -= 5
            elif h["latency_ms"] > 1500:
                resilience_score -= 10

    # Penalización por reportes sociales
    if blackout_count >= 10:
        resilience_score -= 25
    elif blackout_count >= 5:
        resilience_score -= 15
    elif blackout_count >= 2:
        resilience_score -= 5

    resilience_score = max(0, min(100, resilience_score))

    # 4. Determinar nivel general del estado
    if resilience_score >= 85:
        status_text = "ESTABLE"
        severity = "BAJA"
    elif resilience_score >= 60:
        status_text = "DEGRADADO"
        severity = "MEDIA"
    else:
        status_text = "CRÍTICO"
        severity = "ALTA"

    # 5. Generar Alertas Tácticas
    # Alerta 1: Resiliencia General
    avg_latency = int(total_latency / active_hosts_count) if active_hosts_count > 0 else 9999
    alerts.append({
        "title": f"[{severity}] 🔌 RESILIENCIA ELÉCTRICA Y RED: {status_text} ({resilience_score}%)",
        "summary": f"Infraestructura: {len(checked_hosts) - (critical_offline + general_offline)}/{len(checked_hosts)} Online. Latencia Media: {avg_latency}ms. Reportes sociales de apagones: {blackout_count} detectados en las últimas 24h.",
        "link": "https://www.cantv.com.ve",
        "published": datetime.now().isoformat(),
        "source": "🔌 Radar de Resiliencia de Red",
        "type": "cyber_alert",
        "severity": severity,
    })

    # Alerta 2: Nodos Críticos Caídos
    if critical_offline > 0:
        offline_names = [h["name"] for h in checked_hosts if not h["online"] and h["critical"]]
        alerts.append({
            "title": f"[ALTA] 🔌 CORTE DE NODO: {', '.join(offline_names)} OFFLINE",
            "summary": "Nodos de telecomunicaciones críticos no responden. Posible caída de enrutamiento BGP regional, sabotaje de fibra o corte de suministro eléctrico a gran escala.",
            "link": "https://www.patria.org.ve",
            "published": datetime.now().isoformat(),
            "source": "🔌 Radar de Resiliencia de Red",
            "type": "cyber_alert",
            "severity": "ALTA",
        })

    # Alerta 3: Alta densidad de reportes sociales de apagón
    if blackout_count >= 5:
        alerts.append({
            "title": "[MEDIA] 🔌 APAGONES: Reportes inorgánicos densos en Redes Sociales",
            "summary": f"Se interceptaron {blackout_count} publicaciones alertando fallas eléctricas en las últimas horas. Ejemplos recientes: " +
                       "; ".join([f"'{item['title'][:50]}...' ({item['source']})" for item in blackout_data["examples"][:2]]),
            "link": "#",
            "published": datetime.now().isoformat(),
            "source": "🔌 Radar de Resiliencia de Red",
            "type": "cyber_alert",
            "severity": "MEDIA",
        })

    return alerts

def get_network_resilience_data() -> Dict[str, Any]:
    """Envoltura estándar compatible con osint_registry.py."""
    items = get_network_resilience_alerts()
    return {
        "timestamp": datetime.now().isoformat(),
        "sources": {"🔌 Radar de Resiliencia de Red": items},
        "count": len(items)
    }

if __name__ == "__main__":
    print("=== TEST MONITOR DE RESILIENCIA DE RED ===")
    d = get_network_resilience_data()
    print(f"Total Alertas: {d['count']}")
    for i in d["sources"].get("🔌 Radar de Resiliencia de Red", []):
        try:
            print(f"[{i['severity']}] {i['title']}")
            print(f" -> {i['summary']}")
        except UnicodeEncodeError:
            # Fallback para consolas cp1252 de Windows
            clean_title = i['title'].encode('ascii', 'ignore').decode('ascii')
            clean_summary = i['summary'].encode('ascii', 'ignore').decode('ascii')
            print(f"[{i['severity']}] {clean_title}")
            print(f" -> {clean_summary}")
