from datetime import datetime
from typing import Any, Dict, List

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()

VENCERT_URL = "https://vencert.suscerte.gob.ve/alertas/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CobaltoHub/9.0 ThreatIntel"

_vencert_cb = {"disabled": False}


def get_vencert_alerts() -> List[Dict[str, Any]]:
    results = []
    if _vencert_cb["disabled"]:
        return results
    try:
        resp = requests.get(VENCERT_URL, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Las alertas de vencert suelen estar en bloques de artículos o posts
            articles = soup.find_all("article")
            for article in articles[:5]:
                # Encontrar el título (usualmente h2 o h3)
                title_tag = article.find(["h2", "h3"])
                if not title_tag:
                    continue

                title = title_tag.text.strip()
                link = title_tag.find("a")["href"] if title_tag.find("a") else VENCERT_URL

                # Buscar un resumen o fecha
                summary_tag = article.find("p")
                summary = summary_tag.text.strip()[:200] + "..." if summary_tag else "Alerta técnica del estado."

                # Buscar fecha si existe
                date_tag = article.find("time")
                published = (
                    date_tag.get("datetime")
                    if date_tag and date_tag.has_attr("datetime")
                    else datetime.now().isoformat()
                )

                results.append(
                    {
                        "title": f"[OFICIAL] 🇻🇪 VenCERT: {title}",
                        "summary": summary,
                        "link": link,
                        "published": published,
                        "source": "🇻🇪 VenCERT Oficial (Gobierno)",
                        "type": "cyber_alert",
                        "severity": "ALTA" if "crítica" in title.lower() or "crítico" in title.lower() else "MEDIA",
                    }
                )

            # Fallback si el DOM no tiene <article> (puede que usen divs genéricos)
            if not results:
                headers = soup.find_all(["h2", "h3"])
                for h in headers[:5]:
                    title = h.text.strip()
                    if len(title) > 10 and title.lower() not in ["buscar", "menú", "boletines"]:
                        link_tag = h.find("a")
                        link = link_tag["href"] if link_tag else VENCERT_URL
                        results.append(
                            {
                                "title": f"[OFICIAL] 🇻🇪 VenCERT: {title}",
                                "summary": "Alerta técnica publicada por SUSCERTE / VenCERT.",
                                "link": link,
                                "published": datetime.now().isoformat(),
                                "source": "🇻🇪 VenCERT Oficial (Gobierno)",
                                "type": "cyber_alert",
                                "severity": "ALTA"
                                if "crítica" in title.lower() or "crítico" in title.lower()
                                else "MEDIA",
                            }
                        )
        else:
            print(f"[VENCERT-WARN] HTTP {resp.status_code} desde VenCERT. Desactivando consultas estatales.")
            _vencert_cb["disabled"] = True
    except Exception as e:
        print(f"[VENCERT-WARN] Error consultando portal estatal: {e}. Desactivando consultas estatales.")
        _vencert_cb["disabled"] = True

    return results


def get_vencert_data() -> Dict[str, Any]:
    items = get_vencert_alerts()
    return {
        "timestamp": datetime.now().isoformat(),
        "sources": {"🇻🇪 VenCERT Oficial (Gobierno)": items},
        "count": len(items),
    }


if __name__ == "__main__":
    print("=== TEST VENCERT TRACKER ===")
    d = get_vencert_data()
    print(f"Total: {d['count']} alertas detectadas")
    for i in d["sources"].get("🇻🇪 VenCERT Oficial (Gobierno)", []):
        try:
            print(f"- {i['title']}")
        except Exception:
            pass
