from datetime import datetime
from typing import Any, Dict, List

import requests
import urllib3

urllib3.disable_warnings()

RANSOMWARE_API = "https://api.ransomware.live/recentvictims"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CobaltoHub/9.0 ThreatIntel"


def get_ransomware_alerts() -> List[Dict[str, Any]]:
    results = []
    try:
        resp = requests.get(RANSOMWARE_API, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for victim in data[:50]:  # Revisa las últimas 50 víctimas
                country = victim.get("country", "")
                title = victim.get("post_title", "")
                desc = victim.get("description", "")
                group = victim.get("group_name", "Desconocido")

                # Check for Venezuela or LatAm relevance
                is_ve = False
                if country == "VE":
                    is_ve = True
                if any(
                    kw in (title + desc).lower()
                    for kw in ["venezuela", "caracas", "pdvsa", "corpoelec", "cantv", "cne"]
                ):
                    is_ve = True

                # Para propósitos de este radar, si no es VE pero es un leak masivo (ej: gobierno) lo consideramos
                is_critical = "gobierno" in desc.lower() or "government" in desc.lower()

                if is_ve or (is_critical and len(results) < 2):
                    severity = "ALTA" if is_ve else "MEDIA"
                    pub = victim.get("published")
                    ts = pub if pub else datetime.now().isoformat()

                    results.append(
                        {
                            "title": f"[{severity}] 💀 RANSOMWARE ({group}): {title}",
                            "summary": f"País: {country}. {desc[:200]}...",
                            "link": victim.get("post_url", "https://ransomware.live"),
                            "published": ts,
                            "source": "💀 DeepWeb Ransomware Tracker",
                            "type": "ransomware",
                            "severity": severity,
                        }
                    )
    except Exception as e:
        print(f"[RANSOMWARE-WARN] Error consultando API: {e}")

    return results


def get_ransomware_data() -> Dict[str, Any]:
    items = get_ransomware_alerts()
    return {
        "timestamp": datetime.now().isoformat(),
        "sources": {"💀 DeepWeb Ransomware Tracker": items},
        "count": len(items),
    }


if __name__ == "__main__":
    print("=== TEST RANSOMWARE TRACKER ===")
    d = get_ransomware_data()
    print(f"Total: {d['count']} leaks detectados")
    for i in d["sources"].get("💀 DeepWeb Ransomware Tracker", []):
        print(f"{i['title']} -> País: {i['summary'].split('.')[0]}")
