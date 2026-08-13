import os
import re

files = ["main.3abeda0036a2fb0df8cb.js"]

for filepath in files:
    if not os.path.exists(filepath):
        continue
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Find all strings matching /api/
    api_routes = set(re.findall(r"[\'\"](\/api\/[a-zA-Z0-9_\-\/]+)[\'\"]", content))
    print(f"ALL API Routes in {filepath}:")
    for route in sorted(list(api_routes)):
        print(f"  - {route}")

    # Also let's print any URL strings containing /api/
    full_api_urls = set(
        re.findall(r"[\'\"](https?://[a-zA-Z0-9.-]+(?:\:[0-9]+)?\/api\/[a-zA-Z0-9_\-\/]+)[\'\"]", content)
    )
    print(f"\nALL Full API URLs in {filepath}:")
    for url in sorted(list(full_api_urls)):
        print(f"  - {url}")
