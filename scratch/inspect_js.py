import os
import re

files = ["main.3abeda0036a2fb0df8cb.js", "main.3ec5a79432dfb246d94d.js", "main.bac453ad3dbe508f57a1.js"]

results = {}

for f in files:
    if not os.path.exists(f):
        print(f"File {f} not found!")
        continue

    print(f"Analyzing {f}...")
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()

    # Get stats
    size = len(content)

    # Extract domains/URLs
    urls = set(re.findall(r"(https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}[^\s\'\"\\}]*)", content))
    urls = [
        u
        for u in urls
        if "w3.org" not in u and "schema.org" not in u and "webpack" not in u and "ns.adobe.com" not in u
    ]

    # Frameworks / common packages
    frameworks = []
    for lib in [
        "react",
        "angular",
        "vue",
        "rxjs",
        "leaflet",
        "d3",
        "jquery",
        "bootstrap",
        "tailwind",
        "redux",
        "svelte",
    ]:
        if lib in content.lower():
            frameworks.append(lib)

    # Project-specific keywords
    keywords = []
    for kw in [
        "venezuela",
        "noticia",
        "cobalto",
        "cortana",
        "intel",
        "map",
        "chart",
        "admin",
        "user",
        "dashboard",
        "graph",
        "cyber",
        "onion",
        "darknet",
    ]:
        if kw in content.lower():
            keywords.append(kw)

    # Search for specific titles or tags
    # Usually SPA apps have some page/tab title strings in JS
    titles = set(re.findall(r"title\s*:\s*[\'\"]([^\'\"]+)[\'\"]", content))
    titles = list(titles)[:10]

    results[f] = {
        "size": size,
        "frameworks": frameworks,
        "keywords": keywords,
        "urls": list(urls)[:15],
        "titles": titles,
        "first_500": content[:500],
    }

print("\n--- RESULTS ---")
for f, data in results.items():
    print(f"File: {f}")
    print(f"Size: {data['size']} bytes")
    print(f"Frameworks: {data['frameworks']}")
    print(f"Keywords: {data['keywords']}")
    print(f"Titles: {data['titles']}")
    print(f"Sample URLs: {data['urls']}")
    print("-" * 50)
