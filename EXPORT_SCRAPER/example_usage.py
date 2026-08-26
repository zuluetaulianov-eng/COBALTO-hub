"""
EJEMPLO DE USO - EXPORT_SCRAPER
================================
Ejecuta la extracción de datos en vivo de las 5 fuentes exportadas:
1. Hacker News
2. Dark Web & Paste Sites
3. LinkedIn OSINT Dorking
4. Mastodon Federated API
5. Bluesky AT Protocol
"""

import json
import sys

from bluesky_scraper import fetch_bluesky_sync
from darkweb_paste_scraper import analyze_leak_text
from hacker_news_scraper import search_hn_sync
from linkedin_scraper import search_linkedin_sync
from mastodon_scraper import fetch_mastodon_sync


def safe_print(text: str):
    """Evita errores de codificación unicode en consolas Windows de 8 bits."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(sys.stdout.encoding or "ascii", "ignore").decode(sys.stdout.encoding or "ascii"))


def main():
    safe_print("=== 1. Hacker News Scraper ===")
    hn_items = search_hn_sync(query="cybersecurity", limit=3)
    safe_print(f"Resultados HN ({len(hn_items)}):")
    for item in hn_items:
        safe_print(f"  - [{item['points']} pts] {item['title']} -> {item['link']}")
    safe_print("\n")

    safe_print("=== 2. Dark Web & Paste Analysis ===")
    sample_leak = "Leaked DB: admin@example.com:Password123! BTC Wallet: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa OFAC Sanctioned Entity."
    dark_analysis = analyze_leak_text(sample_leak)
    safe_print("Análisis sintáctico de leak/paste:")
    safe_print(json.dumps(dark_analysis, indent=2, ensure_ascii=False))
    safe_print("\n")

    safe_print("=== 3. LinkedIn OSINT Dorking ===")
    li_items = search_linkedin_sync(query="Ciberseguridad Venezuela", search_type="profile", limit=3)
    safe_print(f"Resultados LinkedIn ({len(li_items)}):")
    for item in li_items:
        safe_print(f"  - {item['title']} -> {item['link']}")
    safe_print("\n")

    safe_print("=== 4. Mastodon Federated Scraper ===")
    masto_items = fetch_mastodon_sync(hashtag="infosec", limit=3)
    safe_print(f"Resultados Mastodon ({len(masto_items)}):")
    for item in masto_items:
        safe_print(f"  - [{item['author']}] {item['title']} -> {item['link']}")
    safe_print("\n")

    safe_print("=== 5. Bluesky AT Protocol Scraper ===")
    bsky_items = fetch_bluesky_sync(query="ciberseguridad", limit=3)
    safe_print(f"Resultados Bluesky ({len(bsky_items)}):")
    for item in bsky_items:
        safe_print(f"  - [@{item['author_handle']}] {item['title']} -> {item['link']}")


if __name__ == "__main__":
    main()
