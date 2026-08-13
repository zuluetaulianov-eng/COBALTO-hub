import os
import re

files = ["main.bac453ad3dbe508f57a1.js", "main.3abeda0036a2fb0df8cb.js", "main.3ec5a79432dfb246d94d.js"]


def search_patterns(filepath):
    print(f"\n--- Detailed Analysis of {filepath} ---")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Look for all avl.team endpoints
    avl_urls = set(re.findall(r"https?://[a-zA-Z0-9.-]*avl\.team[^\s\'\"\\}]*", content))
    print("AVL.team API Endpoints found:")
    for url in sorted(list(avl_urls)):
        print(f"  - {url}")

    # 2. Look for any other custom HTTP/HTTPS URLs (excluding momentjs, angular, etc.)
    all_urls = set(re.findall(r"(https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}[^\s\'\"\\}]*)", content))
    custom_urls = []
    for url in all_urls:
        # Ignore common libraries
        if any(
            lib in url
            for lib in [
                "w3.org",
                "schema.org",
                "webpack",
                "angular",
                "momentjs",
                "via.placeholder",
                "quilljs",
                "vk.com",
                "t.me",
            ]
        ):
            continue
        custom_urls.append(url)
    print("Other Custom/Project Endpoints:")
    for url in sorted(custom_urls)[:10]:
        print(f"  - {url}")

    # 3. Look for Venezuelan references or custom search keywords
    vzla_refs = set(re.findall(r"(?i)(venezuela|caracas|maduro|noticia|chavez|guaido)", content))
    print(f"Venezuela/Spanish context keywords: {list(vzla_refs)}")

    # 4. Russian terms translated
    # Let's search for "Лавина" or "Пульс" in unicode or raw Russian
    rus_matches = []
    for term in ["Лавина", "Пульс", "avalanche", "pulse"]:
        if term.lower() in content.lower():
            rus_matches.append(term)
    print(f"System names found: {rus_matches}")


for f in files:
    if os.path.exists(f):
        search_patterns(f)
    else:
        print(f"File {f} not found!")
