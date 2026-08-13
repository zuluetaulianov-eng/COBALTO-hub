import re
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
import urllib3
from dotenv import load_dotenv

load_dotenv()
urllib3.disable_warnings()

PASTEBIN_SCRAPE = "https://scrape.pastebin.com/api_scraping.php"
PASTEBIN_RAW = "https://scrape.pastebin.com/api_scraping/raw/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CobaltoHub/9.0"
MAX_PASTES = 15

VE_KEYWORDS = [
    "venezuela",
    "maduro",
    "guido",
    "machado",
    "cne",
    "psuv",
    "fanb",
    "pdvsa",
    "dolar",
    "bcv",
    "esequibo",
    "caracas",
    "maracaibo",
    "petro",
    "sancion",
    "eeuu",
    "ofac",
    "gobierno",
    "oposicion",
    "militares",
    "preso politico",
    "exilio",
    "migrante",
    "tancol",
    "el nino",
    "alba",
    "crip",
    "clap",
    "carnet de la patria",
    "filtracion",
    "leak",
    "database",
    "dump",
    "credential",
    "password",
    "correo",
    "gobierno",
    "documento",
    "confidencial",
]

SEVERITY_KEYWORDS = {
    "alta": [
        "database",
        "dump",
        "credential",
        "password",
        "sql",
        "filtracion",
        "leak",
        "confidencial",
        "secreto",
        "clasificado",
    ],
    "media": ["documento", "correo", "interno", "reporte", "informe", "lista", "base de datos"],
}


def _match_ve(text: str) -> List[str]:
    t = text.lower()
    found = []
    for kw in VE_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", t):
            found.append(kw)
    return found


def _classify_severity(text: str) -> str:
    t = text.lower()
    for kw in SEVERITY_KEYWORDS["alta"]:
        if kw in t:
            return "ALTA"
    for kw in SEVERITY_KEYWORDS["media"]:
        if kw in t:
            return "MEDIA"
    return "BAJA"


def get_pastebin_pastes() -> List[Dict[str, Any]]:
    results = []
    try:
        resp = requests.get(PASTEBIN_SCRAPE, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.status_code != 200:
            return results
        pastes = resp.json()
        for p in pastes[:MAX_PASTES]:
            key = p.get("key", "")
            title = (p.get("title") or "").strip()
            date_raw = p.get("date", 0)
            size = p.get("size", 0)
            if not key:
                continue
            text_to_check = f"{title}"
            if size and isinstance(size, (int, float)) and size < 50000:
                try:
                    raw_resp = requests.get(f"{PASTEBIN_RAW}{key}", headers={"User-Agent": USER_AGENT}, timeout=5)
                    if raw_resp.status_code == 200:
                        text_to_check += " " + raw_resp.text[:2000]
                except Exception:
                    pass
            matches = _match_ve(text_to_check)
            if not matches:
                continue
            severity = _classify_severity(text_to_check)
            ts = (
                datetime.fromtimestamp(int(date_raw), tz=timezone.utc).isoformat()
                if date_raw
                else datetime.now().isoformat()
            )
            results.append(
                {
                    "title": f"[{severity}] {title[:100] if title else 'Pastebin anónimo'}",
                    "summary": f"Keywords: {', '.join(matches[:5])} | Tamaño: {size} bytes | Key: {key}",
                    "link": f"https://pastebin.com/{key}",
                    "published": ts,
                    "source": "📋 Pastebin Monitor",
                    "type": "pastebin",
                    "severity": severity,
                }
            )
    except Exception as e:
        print(f"[PASTEBIN-WARN] Error: {e}")
    return results


def get_pastebin_data() -> Dict[str, Any]:
    items = get_pastebin_pastes()
    return {"timestamp": datetime.now().isoformat(), "sources": {"📋 Pastebin Monitor": items}, "count": len(items)}


if __name__ == "__main__":
    print("=== TEST PASTEBIN ===")
    d = get_pastebin_data()
    print(f"Total: {d['count']} items")
    for i in d["sources"].get("📋 Pastebin Monitor", []):
        print(f"  [{i['severity']}] {i['title'][:60]}...")
