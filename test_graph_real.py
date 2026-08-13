import json
import sys

from osint_socialgraph import get_social_graph

try:
    with open('dashboard_persistent_cache.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    entries = data.get('all_entries', [])
    print(f"Total entries loaded: {len(entries)}")

    if not entries:
        print("No entries in cache!")
        sys.exit(1)

    res = get_social_graph(entries, use_ai=False)
    nodes = res["graph"]["nodes"]
    edges = res["graph"]["edges"]

    print(f"NODOS: {len(nodes)}")
    print(f"EDGES: {len(edges)}")

    for n in nodes[:5]:
        print("Node:", n["id"])

except Exception as e:
    print("Error:", e)
