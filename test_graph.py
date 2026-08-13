from extractor import get_own_intel
from osint_socialgraph import get_social_graph

entries = get_own_intel()
if not entries:
    entries = [{"title": "Maduro dice algo sobre Maria Corina", "summary": "Un texto de prueba"}]

res = get_social_graph(entries, use_ai=False)
print("NODOS:", len(res["graph"]["nodes"]))
print("EDGES:", len(res["graph"]["edges"]))
