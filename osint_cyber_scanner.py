import time
from datetime import datetime
from typing import Any, Dict, List

import requests
import urllib3

urllib3.disable_warnings()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CobaltoHub/9.0 CyberScanner"

# Target list: Infraestructura crítica
TARGETS = [
    {"name": "Banco Central de Vzla (BCV)", "url": "https://www.bcv.org.ve", "type": "banca"},
    {"name": "Ministerio de Defensa (MPPD)", "url": "http://www.mppd.gob.ve", "type": "militar"},
    {"name": "CNE Electoral", "url": "http://www.cne.gob.ve", "type": "electoral"},
    {"name": "PDVSA", "url": "http://www.pdvsa.com", "type": "infra"},
    {"name": "CANTV", "url": "https://www.cantv.com.ve", "type": "telecom"},
]


def scan_targets() -> List[Dict[str, Any]]:
    results = []
    for t in TARGETS:
        try:
            start_time = time.time()
            resp = requests.get(t["url"], headers={"User-Agent": USER_AGENT}, timeout=8)
            latency = int((time.time() - start_time) * 1000)

            if resp.status_code >= 500:
                severity = "ALTA"
                summary = f"Servidor retornó HTTP {resp.status_code}. Posible ataque de denegación de servicio (DDoS) o defacement activo."
            elif latency > 6000:
                severity = "MEDIA"
                summary = f"Latencia crítica detectada ({latency}ms). Posible saturación de red o ciberataque en curso."
            else:
                continue  # Todo normal

            results.append(
                {
                    "title": f"[{severity}] 🚨 ALERTA CYBER: {t['name']} Degradado",
                    "summary": summary,
                    "link": t["url"],
                    "published": datetime.now().isoformat(),
                    "source": "💻 Monitor Cyber Activo",
                    "type": "cyber_alert",
                    "severity": severity,
                }
            )
        except requests.exceptions.Timeout:
            results.append(
                {
                    "title": f"[ALTA] 🚨 ALERTA CYBER: {t['name']} OFFLINE",
                    "summary": "El servidor no respondió tras 8 segundos (TIMEOUT). Falla masiva de infraestructura o ataque DDoS agresivo.",
                    "link": t["url"],
                    "published": datetime.now().isoformat(),
                    "source": "💻 Monitor Cyber Activo",
                    "type": "cyber_alert",
                    "severity": "ALTA",
                }
            )
        except requests.exceptions.RequestException as e:
            results.append(
                {
                    "title": f"[ALTA] 🚨 ALERTA CYBER: {t['name']} INACCESIBLE",
                    "summary": f"Conexión rechazada o ruteo destruido. Servidor colapsado. Info: {str(e)[:60]}",
                    "link": t["url"],
                    "published": datetime.now().isoformat(),
                    "source": "💻 Monitor Cyber Activo",
                    "type": "cyber_alert",
                    "severity": "ALTA",
                }
            )
    return results


def get_cyber_scanner_data() -> Dict[str, Any]:
    items = scan_targets()
    return {"timestamp": datetime.now().isoformat(), "sources": {"💻 Monitor Cyber Activo": items}, "count": len(items)}


if __name__ == "__main__":
    print("=== TEST CYBER SCANNER ===")
    d = get_cyber_scanner_data()
    print(f"Detectadas {d['count']} vulnerabilidades/caídas.")
    for i in d["sources"]["💻 Monitor Cyber Activo"]:
        print(f"{i['title']} -> {i['summary']}")
