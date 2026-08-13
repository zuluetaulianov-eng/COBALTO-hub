import asyncio
import json
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import community as community_louvain
import networkx as nx
from dotenv import load_dotenv
from openai import AsyncOpenAI as AsyncGroq

from ai_core import analyze_sentiment
from graph_database import (
    compare_snapshots,
    get_latest_snapshot,
    get_node_history,
    get_recent_snapshots,
    save_graph_snapshot,
)
from utils import safe_async_run

load_dotenv()
logger = logging.getLogger(__name__)

PERSON_KEYWORDS = [
    "maduro",
    "machado",
    "guaido",
    "capriles",
    "cabello",
    "rodriguez",
    "delcy",
    "padrino",
    "remigio",
    "cesar",
    "tareck",
    "el aissami",
    "marco rubio",
    "trump",
    "biden",
    "putin",
    "xi jinping",
    "lula",
    "petro",
    "noboa",
    "milei",
    "mauro",
    "lopez obrador",
    "boric",
    "arnaud",
    "edmundo",
    "gonzalez",
    "urrutia",
    "nicolas",
    "presidente",
    "ministro",
    "general",
    "almirante",
    "gobernador",
    "alcalde",
    "diputado",
    "senador",
    "congresista",
    "canciller",
    "embajador",
    "corina yoris",
    "luis eduardo martinez",
    "jose noriega",
    "maria corina machado",
    "henrique capriles",
    "antonio ledezma",
    "leopoldo lopez",
    "juan guaido",
    "jorge rodriguez",
    "diosdado cabello",
    "nicolas maduro",
    "cilia flores",
    "delcy rodriguez",
    "tito chaderton",
    "samuel moncada",
    "vladimir padrino",
    "vladimir padrino lopez",
    "domingo hernandez lares",
    "remigio ceballos",
    "juan carlos rodriguez",
    "antonio benavides",
    "gustavo gonzalez lopez",
    "jose adelnar figueroa",
    "jose vicente rangel silva",
    "alejandro betancourt",
    "raul gorrin",
    "diego salazar",
    "carlos erik malpica",
    "rafael ramirez",
    "eulogio del pino",
    "nelson martinez",
    "asdrubal chavez",
    "joe biden",
    "kamala harris",
    "anthony blinken",
    "rick scott",
    "bob menendez",
    "gustavo petro",
    "nayib bukele",
    "daniel ortega",
    "miguel diaz-canel",
    "emmanuel macron",
    "pedro sanchez",
    "olaf scholz",
    "rishi sunak",
]

ORG_KEYWORDS = [
    "fanb",
    "pdvsa",
    "bcv",
    "cne",
    "tsj",
    "psuv",
    "vpitv",
    "oea",
    "onu",
    "fmi",
    "cpi",
    "farc",
    "eln",
    "greenwich",
    "cabal",
    "southern district",
    "ofac",
    "dea",
    "cia",
    "nasa",
    "firms",
    "acled",
    "unodc",
    "human rights watch",
    "gobierno",
    "oposicion",
    "amnesty international",
    "ipys",
    "espacio publico",
    "transparencia",
    "fedecamaras",
    "fvt",
    "conindustria",
    # Gubernamentales y estatales
    "asamblea nacional",
    "consejo nacional electoral",
    "tribunal supremo de justicia",
    "procuraduria general",
    "contraloria general",
    "defensoria del pueblo",
    "ministerio del poder popular",
    "gabinete ministerial",
    "vicepresidencia",
    # Empresas estatales
    "corporacion electrica nacional",
    "cantv",
    "conviasa",
    "casa de la moneda",
    "bauxilum",
    "ferrominera",
    "venesalud",
    "instituto de seguros sociales",
    # Infraestructura crítica
    "refineria el palito",
    "refineria cardon",
    "centro de refinacion paraguana",
    "complexo criogenico de jose",
    "sistema interconectado nacional",
    "hidroelectrico guri",
    "hidroelectrico simon bolivar",
    "aeropuerto maiquetia",
    # Grupos armados y crimen organizado
    "disidencias del farc",
    "megabanda",
    "tren de aragua",
    "megabanda el train",
    "cartel de los soles",
    "colectivos",
    "la primera linea",
    "frente bolivariano",
    # ONGs y sociedad civil
    "provea",
    "foro penal",
    "observatorio venezolano de violencia",
    "transparencia venezuela",
    "sindicato nacional de trabajadores",
    "confederacion de trabajadores de venezuela",
    # Internacionales
    "union europea",
    "grupo de lima",
    "oesa",
    "bancos centrales",
    "banco mundial",
    "bid",
    "caf",
    "opci",
    "unicef",
    "oms",
    "oit",
    "acnur",
]

LOCATION_KEYWORDS = [
    "venezuela",
    "caracas",
    "maracaibo",
    "valencia",
    "barquisimeto",
    "ciudad bolivar",
    "merida",
    "san cristobal",
    "barcelona",
    "cumana",
    "puerto ordaz",
    "margarita",
    "isla de margarita",
    "los teques",
    "maracay",
    "puerto la cruz",
    "guayana",
    "tachira",
    "zulia",
    "bolivar",
    "esequibo",
    "guyana",
    "colombia",
    "brasil",
    "frontera",
    "el callao",
    "tumeremo",
    "el dorado",
    "punto fijo",
    "la guaira",
    "las cadenas",
    "caura",
    "orinoco",
    # Infraestructura estratégica
    "complejo industrial jose antonio anzoategui",
    "puerto de la guaira",
    "puerto de puerto cabello",
    "puerto de maracaibo",
    "aeropuerto simon bolivar",
    "aeropuerto la chinita",
    "aeropuerto alberto carnevalli",
    # Fronteras y zonas conflictivas
    "arco minero del orinoco",
    "estado amazonas",
    "estado delta amacuro",
    "frontera tachira",
    "frontera zulia",
    "frontera apure",
    "frontera bolivar",
    "frontera sucre",
    "frontera monagas",
    "frontera anzoategui",
    # Zonas industriales
    "ciudad industrial valencia",
    "parque industrial san vicente",
    "parque industrial guayana",
    "zona industrial matanzas",
    "zona industrial los ruices",
]

# Palabras clave para clasificación de aristas
CONFLICT_KEYWORDS = [
    "denuncia",
    "ataca",
    "critica",
    "enfrenta",
    "opone",
    "condena",
    "acusación",
    "conflicto",
    "guerra",
    "lucha",
    "disputa",
    "crisis",
    "sanciones",
    "protesta",
    "repudia",
    "rechazo",
]

# Nuevas categorías de keywords para mayor cobertura
ECONOMIC_KEYWORDS = [
    "petro",
    "dolar",
    "inflacion",
    "hiperinflacion",
    "devaluacion",
    "cambio",
    "bcv",
    "reservas internacionales",
    "pib",
    "produccion petrolera",
    "cuota opep",
    "sancciones",
    "bloqueo",
    "embargo",
    "confiscacion",
    "cripto",
    "bitcoin",
    "usdt",
    "binance",
    "remesas",
    "divisas",
]

SECURITY_KEYWORDS = [
    "secuestro",
    "extorsion",
    "homicidio",
    "robo",
    "asalto",
    "violencia",
    "delincuencia",
    "narcotrafico",
    "lavado de dinero",
    "corrupcion",
    "fraude",
    "contrabando",
    "guerrilla",
    "paramilitares",
    "desplazamiento",
    "migracion",
    "refugiados",
    "exodo",
    "frontera",
    "trafico",
]

INFRASTRUCTURE_KEYWORDS = [
    "apagon",
    "corte de luz",
    "servicio basico",
    "agua",
    "gas",
    "internet",
    "conexion",
    "senal",
    "telefonia",
    "transporte",
    "gasolina",
    "diesel",
    "combustible",
    "escasez",
    "colas",
    "abastecimiento",
    "distribucion",
]

ALLIANCE_KEYWORDS = [
    "acuerdo",
    "alianza",
    "apoya",
    "colabora",
    "coopera",
    "firmó",
    "unión",
    "pacto",
    "tratado",
    "respalda",
    "junto",
    "aliado",
    "colaboración",
    "participación",
    "integración",
]

ALL_KNOWLEDGE = {
    w.lower()
    for w in PERSON_KEYWORDS
    + ORG_KEYWORDS
    + LOCATION_KEYWORDS
    + ECONOMIC_KEYWORDS
    + SECURITY_KEYWORDS
    + INFRASTRUCTURE_KEYWORDS
}
for w in list(ALL_KNOWLEDGE):
    if " " in w:
        ALL_KNOWLEDGE.update(w.split())

# Configuración IA
USE_AI_EXTRACTION = os.getenv("USE_AI_EXTRACTION", "true").lower() == "true"
ENABLE_GRAPH_PERSISTENCE = os.getenv("ENABLE_GRAPH_PERSISTENCE", "true").lower() == "true"
ENABLE_SEMANTIC_EDGES = os.getenv("ENABLE_SEMANTIC_EDGES", "true").lower() == "true"
ENABLE_ALERTS = os.getenv("ENABLE_ALERTS", "true").lower() == "true"

# Umbrales para alertas
ALERT_THRESHOLDS = {
    "node_growth_rate": 0.5,  # 50% crecimiento en nodos
    "edge_growth_rate": 0.5,  # 50% crecimiento en aristas
    "centrality_spike": 0.3,  # 30% aumento en centralidad
    "new_critical_nodes": 3,  # Más de 3 nodos nuevos con alta centralidad
    "community_split": 0.3,  # 30% cambio en estructura de comunidades
}


async def _extract_entities_ai(text: str) -> Dict[str, List[str]]:
    """Extracción de entidades usando Groq Llama 3.3 para NER dinámico."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return _extract_entities_regex(text)

    try:
        client = AsyncGroq(api_key=api_key, base_url="https://integrate.api.nvidia.com/v1")
        prompt = f"""Extrae entidades nombradas de este texto sobre Venezuela.
Devuelve ÚNICAMENTE un JSON válido con este formato:
{{"persons": [], "organizations": [], "locations": []}}
Solo incluye entidades relevantes para el contexto político/económico/militar.
Texto: {text[:1000]}"""

        import config

        response = await client.chat.completions.create(
            model=config.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        content = response.choices[0].message.content.strip()
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            result = json.loads(content[start:end])
            # Limitar a 5 por categoría
            return {
                "persons": result.get("persons", [])[:5],
                "organizations": result.get("organizations", [])[:5],
                "locations": result.get("locations", [])[:5],
            }
    except Exception as e:
        print(f"[WARN] Error en extracción IA, usando fallback regex: {e}")

    return _extract_entities_regex(text)


def _extract_entities_regex(text: str) -> Dict[str, List[str]]:
    t = text.lower()
    found_persons = {}
    found_orgs = {}
    found_locs = {}
    all_keywords = (
        [(kw, "person") for kw in PERSON_KEYWORDS]
        + [(kw, "org") for kw in ORG_KEYWORDS]
        + [(kw, "loc") for kw in LOCATION_KEYWORDS]
    )
    all_keywords.sort(key=lambda x: len(x[0]), reverse=True)
    for kw, cat in all_keywords:
        pattern = r"(?<!\w)" + re.escape(kw) + r"(?!\w)"
        if re.search(pattern, t):
            t = re.sub(pattern, lambda m: " " * len(m.group()), t, count=1)
            if cat == "person":
                found_persons[kw.title()] = True
            elif cat == "org":
                found_orgs[kw.upper()] = True
            elif cat == "loc":
                found_locs[kw.title()] = True
    matched_kws = set(found_persons) | set(found_orgs) | set(found_locs)
    capitals = re.findall(r"\b[A-Z][a-záéíóúüñ]{3,}\b", text)
    seen_lower = {w.lower() for w in matched_kws}
    for kw in list(seen_lower):
        seen_lower.update(kw.split())
    for c in capitals:
        cl = c.lower()
        if cl not in ALL_KNOWLEDGE and cl not in seen_lower:
            seen_lower.add(cl)
            found_locs[c] = True
    return {
        "persons": list(found_persons.keys())[:20],
        "organizations": list(found_orgs.keys())[:20],
        "locations": list(found_locs.keys())[:20],
    }


async def _extract_entities_hybrid(text: str) -> Dict[str, List[str]]:
    """Extracción híbrida: IA si está disponible, sino regex."""
    if USE_AI_EXTRACTION:
        return await _extract_entities_ai(text)
    return _extract_entities_regex(text)


async def _extract_entities_and_sentiments_batch_async(entries_subset: List[Dict]) -> List[Tuple[Dict, Dict]]:
    """Extrae entidades y calcula sentimientos para un lote de entradas de forma concurrente (evita el problema N+1)."""
    entity_tasks = []
    sentiment_tasks = []
    for entry in entries_subset:
        text = f"{entry.get('title', '')} {entry.get('summary', '')}"
        entity_tasks.append(_extract_entities_hybrid(text))
        sentiment_tasks.append(analyze_sentiment(text))

    entity_results = await asyncio.gather(*entity_tasks, return_exceptions=True)
    sentiment_results = await asyncio.gather(*sentiment_tasks, return_exceptions=True)
    entity_results = [r if not isinstance(r, Exception) else {} for r in entity_results]
    sentiment_results = [r if not isinstance(r, Exception) else 0.0 for r in sentiment_results]
    return list(zip(entity_results, sentiment_results))


def _build_graph(entries: List[Dict], use_ai: bool = False) -> Dict:
    edges = defaultdict(int)
    edge_details = defaultdict(list)
    entity_mentions = defaultdict(int)  # Frecuencia de mención
    entity_sentiments = defaultdict(list)  # Sentimientos por entidad

    entries_subset = entries[:60]

    if use_ai:
        try:
            batch_results = safe_async_run(_extract_entities_and_sentiments_batch_async(entries_subset))
        except Exception as e:
            logger.error(f"Fallo en la extracción de entidades por lote de IA: {e}")
            # Fallback a procesamiento regex y sentimiento neutro individual
            batch_results = [
                (
                    _extract_entities_regex(f"{entry.get('title', '')} {entry.get('summary', '')}"),
                    {"sentiment": "neutral", "score": 0, "confidence": 0},
                )
                for entry in entries_subset
            ]
    else:
        batch_results = [
            (
                _extract_entities_regex(f"{entry.get('title', '')} {entry.get('summary', '')}"),
                {"sentiment": "neutral", "score": 0, "confidence": 0},
            )
            for entry in entries_subset
        ]

    for idx, entry in enumerate(entries_subset):
        f"{entry.get('title', '')} {entry.get('summary', '')}"
        entities, sentiment_result = batch_results[idx]

        all_ents = []
        cats = {}
        for cat, items in entities.items():
            for item in items:
                if item:
                    entity_key = f"{cat}::{item}"
                    all_ents.append(entity_key)
                    cats[entity_key] = cat
                    # Contar frecuencia de mención
                    entity_mentions[entity_key] += 1

        # Asignar sentimiento a entidades mencionadas
        for entity_key in all_ents:
            entity_sentiments[entity_key].append(sentiment_result)

        for i in range(len(all_ents)):
            for j in range(i + 1, len(all_ents)):
                a, b = all_ents[i], all_ents[j]
                if a < b:
                    key = (a, b)
                else:
                    key = (b, a)
                edges[key] += 1
                if len(edge_details[key]) < 2:
                    edge_details[key].append(entry.get("title", ""))

    all_entity_keys = set()
    for ents in entity_mentions:
        all_entity_keys.add(ents)
    orphan_nodes = []
    for a, b in list(edges.keys()):
        all_entity_keys.discard(a)
        all_entity_keys.discard(b)
    for orphan_key in all_entity_keys:
        cat, label = orphan_key.split("::", 1)
        color = "#FF2D55" if cat == "persons" else "#00E5FF" if cat == "locations" else "#B388FF"
        orphan_nodes.append(
            {
                "id": orphan_key,
                "label": label,
                "group": cat,
                "color": color,
                "value": entity_mentions.get(orphan_key, 1),
            }
        )

    nodes = []
    node_ids = set()
    for (a, b), w in edges.items():
        for name in [a, b]:
            cat, label = name.split("::", 1)
            if name not in node_ids:
                node_ids.add(name)
                color = "#FF2D55" if cat == "persons" else "#00E5FF" if cat == "locations" else "#B388FF"
                nodes.append({"id": name, "label": label, "group": cat, "color": color, "value": 1})
            else:
                for n in nodes:
                    if n["id"] == name:
                        n["value"] = n.get("value", 1) + 1
                        break

    edges_list = []
    for (a, b), w in edges.items():
        if w >= 1:  # Reducido de 2 a 1 para permitir conexiones con co-ocurrencia única
            # Clasificar tipo de arista semántica
            edge_text = " ".join(edge_details[(a, b)])
            edge_type = _classify_edge_type(edge_text, a, b) if ENABLE_SEMANTIC_EDGES else "co-occurrence"

            edges_list.append(
                {
                    "from": a,
                    "to": b,
                    "width": min(w, 5),
                    "title": ", ".join(edge_details[(a, b)][:2]),
                    "type": edge_type,
                    "color": _get_edge_color(edge_type),
                }
            )

    # Añadir entidades huérfanas (sin aristas) como nodos con valor 1
    orphan_ids = {n["id"] for n in nodes}
    for on in orphan_nodes:
        if on["id"] not in orphan_ids:
            nodes.append(on)

    # Recortar nodos y aristas a los límites de visualización antes de construir el grafo de NetworkX
    # (Evita la explosión de costo computacional O(V^2) en layouts y métricas de NetworkX)
    nodes = nodes[:80]
    node_ids_subset = {n["id"] for n in nodes}
    edges_list = [e for e in edges_list if e["from"] in node_ids_subset and e["to"] in node_ids_subset][:120]

    # Instanciar y construir el grafo de NetworkX una sola vez para evitar redundancia (CPU-bound optimization)
    g = nx.Graph()
    for node in nodes:
        g.add_node(node["id"])
    for edge in edges_list:
        g.add_edge(edge["from"], edge["to"], weight=edge.get("width", 1))

    # Calcular métricas de centralidad con NetworkX pasando el grafo G pre-construido
    graph_metrics = _calculate_centrality_metrics(g)

    # Detectar comunidades con Louvain pasando el grafo G pre-construido
    communities = _detect_communities(g)

    # Enriquecer nodos con métricas, comunidades, frecuencia y sentimiento
    for node in nodes:
        node_id = node["id"]
        if node_id in graph_metrics:
            node.update(graph_metrics[node_id])
        if node_id in communities:
            node["community"] = communities[node_id]
            node["community_color"] = _get_community_color(communities[node_id])
        # Agregar frecuencia de mención
        node["mention_frequency"] = entity_mentions.get(node_id, 0)
        # Agregar sentimiento promedio
        if node_id in entity_sentiments:
            sentiments = entity_sentiments[node_id]
            avg_score = sum(s.get("score", 0) for s in sentiments) / len(sentiments) if sentiments else 0
            # Determinar sentimiento dominante
            sentiment_counts = Counter(s.get("sentiment", "neutral") for s in sentiments)
            dominant_sentiment = sentiment_counts.most_common(1)[0][0] if sentiment_counts else "neutral"
            node["sentiment"] = dominant_sentiment
            node["sentiment_score"] = round(avg_score, 3)
            node["sentiment_confidence"] = (
                round(sum(s.get("confidence", 0) for s in sentiments) / len(sentiments), 3) if sentiments else 0
            )
        else:
            node["sentiment"] = "neutral"
            node["sentiment_score"] = 0
            node["sentiment_confidence"] = 0

    # Calcular layouts alternativos pasando el grafo G pre-construido
    layouts = {
        "force": _calculate_layout(g, "spring"),
        # Los otros layouts se pueden calcular bajo demanda si es necesario
    }

    return {
        "nodes": nodes,
        "edges": edges_list,
        "metrics": graph_metrics,
        "communities": communities,
        "entity_mentions": dict(entity_mentions),
        "layouts": layouts,
    }


def _detect_communities(g: nx.Graph) -> Dict[str, int]:
    """Detecta comunidades usando algoritmo Louvain (acepta un grafo pre-construido)."""
    try:
        if g.number_of_nodes() == 0:
            return {}

        # Algoritmo Louvain para detección de comunidades
        partition = community_louvain.best_partition(g, weight="weight")

        return partition
    except Exception as e:
        print(f"[WARN] Error detectando comunidades: {e}")
        return {}


def _classify_edge_type(text: str, entity_a: str, entity_b: str) -> str:
    """Clasifica el tipo de arista basado en el texto y las entidades."""
    text_lower = text.lower()

    # Verificar si es location-based (una entidad es ubicación)
    cat_a = entity_a.split("::")[0] if "::" in entity_a else ""
    cat_b = entity_b.split("::")[0] if "::" in entity_b else ""

    if cat_a == "locations" or cat_b == "locations":
        return "location"

    # Verificar palabras de conflicto
    if any(kw in text_lower for kw in CONFLICT_KEYWORDS):
        return "conflict"

    # Verificar palabras de alianza
    if any(kw in text_lower for kw in ALLIANCE_KEYWORDS):
        return "alliance"

    # Por defecto: co-occurrence
    return "co-occurrence"


def _get_edge_color(edge_type: str) -> str:
    """Devuelve un color según el tipo de arista."""
    colors = {"co-occurrence": "#888888", "conflict": "#FF2D55", "alliance": "#00FF88", "location": "#00E5FF"}
    return colors.get(edge_type, "#888888")


def _get_community_color(community_id: int) -> str:
    """Genera un color consistente para cada comunidad."""
    colors = [
        "#FF2D55",
        "#00E5FF",
        "#B388FF",
        "#00FF88",
        "#FF9500",
        "#FFCC00",
        "#FF3B30",
        "#5856D6",
        "#007AFF",
        "#4CD964",
        "#FF2D55",
        "#8E8E93",
        "#C7C7CC",
        "#E5E5EA",
        "#AF52DE",
    ]
    return colors[community_id % len(colors)]


def _calculate_layout(g: nx.Graph, layout_type: str = "force") -> Dict[str, Tuple[float, float]]:
    """Calcula coordenadas de layout para diferentes algoritmos de visualización (acepta un grafo pre-construido)."""
    try:
        if g.number_of_nodes() == 0:
            return {}

        pos = {}

        if layout_type == "circular":
            pos = nx.circular_layout(g)
        elif layout_type == "hierarchical":
            # Usar spectral layout como aproximación jerárquica
            pos = nx.spectral_layout(g)
        elif layout_type == "kamada_kawai":
            pos = nx.kamada_kawai_layout(g, weight="weight")
        elif layout_type == "spring":
            pos = nx.spring_layout(g, weight="weight", k=0.3, iterations=50)
        else:
            # Por defecto: force-directed (spring)
            pos = nx.spring_layout(g, weight="weight", k=0.3, iterations=50)

        # Normalizar coordenadas a rango 0-1
        if pos:
            x_values = [p[0] for p in pos.values()]
            y_values = [p[1] for p in pos.values()]

            if x_values and y_values:
                x_min, x_max = min(x_values), max(x_values)
                y_min, y_max = min(y_values), max(y_values)

                x_range = x_max - x_min if x_max != x_min else 1
                y_range = y_max - y_min if y_max != y_min else 1

                pos = {
                    node_id: (
                        (x - x_min) / x_range if x_range > 0 else 0.5,
                        (y - y_min) / y_range if y_range > 0 else 0.5,
                    )
                    for node_id, (x, y) in pos.items()
                }

        return pos
    except Exception as e:
        print(f"[WARN] Error calculando layout {layout_type}: {e}")
        return {}


def _calculate_centrality_metrics(g: nx.Graph) -> Dict[str, Dict]:
    """Calcula métricas de centralidad usando NetworkX (acepta un grafo pre-construido)."""
    try:
        if g.number_of_nodes() == 0:
            return {}

        metrics = {}

        # Degree Centrality (nodos más conectados)
        degree_centrality = nx.degree_centrality(g)

        # Betweenness Centrality (puentes entre comunidades)
        betweenness_centrality = nx.betweenness_centrality(g, weight="weight")

        # Closeness Centrality (cercanía a todos los demás nodos)
        try:
            closeness_centrality = nx.closeness_centrality(g)
        except Exception:
            closeness_centrality = {}

        # Eigenvector Centrality (influencia basada en conexiones influyentes)
        try:
            eigenvector_centrality = nx.eigenvector_centrality(g, max_iter=100)
        except Exception:
            eigenvector_centrality = {}

        # PageRank
        try:
            pagerank = nx.pagerank(g, weight="weight")
        except Exception:
            pagerank = {}

        # Agregar métricas a cada nodo
        for node_id in g.nodes():
            metrics[node_id] = {
                "degree_centrality": round(degree_centrality.get(node_id, 0), 4),
                "betweenness_centrality": round(betweenness_centrality.get(node_id, 0), 4),
                "closeness_centrality": round(closeness_centrality.get(node_id, 0), 4),
                "eigenvector_centrality": round(eigenvector_centrality.get(node_id, 0), 4),
                "pagerank": round(pagerank.get(node_id, 0), 4),
            }

        return metrics
    except Exception as e:
        print(f"[WARN] Error calculando métricas de centralidad: {e}")
        return {}


def get_social_graph(
    entries: List[Dict], use_ai: bool = False, save_snapshot: bool = True, layout_type: str = "force"
) -> Dict[str, Any]:
    graph = _build_graph(entries, use_ai=use_ai)

    try:
        from osint_botnet_detector import tag_botnet_nodes
        graph = tag_botnet_nodes(graph)
    except Exception as e:
        print(f"[WARN] Error etiquetando nodos botnet: {e}")

    # Debug logging
    print(f"[GRAPH] {len(graph.get('nodes', []))} nodes, {len(graph.get('edges', []))} edges")

    communities = graph.get("communities", {})
    community_count = len(set(communities.values())) if communities else 0

    # Aplicar layout seleccionado
    layouts = graph.get("layouts", {})
    selected_layout = layouts.get(layout_type, layouts.get("force", {}))

    # Agregar coordenadas del layout a los nodos
    if selected_layout:
        for node in graph["nodes"]:
            node_id = node["id"]
            if node_id in selected_layout:
                node["x"] = selected_layout[node_id][0]
                node["y"] = selected_layout[node_id][1]

    result = {
        "graph": graph,
        "timestamp": datetime.now().isoformat(),
        "count": len(graph.get("nodes", [])),
        "edges": len(graph.get("edges", [])),
        "extraction_method": "ai" if use_ai else "regex",
        "community_count": community_count,
        "layout_type": layout_type,
        "available_layouts": list(layouts.keys()) if layouts else ["force"],
    }

    # Guardar snapshot si está habilitado
    if save_snapshot and ENABLE_GRAPH_PERSISTENCE:
        try:
            snapshot_id = save_graph_snapshot(graph, result["extraction_method"])
            result["snapshot_id"] = snapshot_id
            result["persistence_enabled"] = True
        except Exception as e:
            print(f"[WARN] Error guardando snapshot: {e}")
            result["persistence_enabled"] = False
    else:
        result["persistence_enabled"] = False

    return result


def get_graph_history(hours: int = 24) -> List[Dict]:
    """Obtiene el historial de snapshots de las últimas N horas."""
    return get_recent_snapshots(hours)


def get_node_evolution(node_id: str, hours: int = 168) -> List[Dict]:
    """Obtiene la evolución de métricas de un nodo específico."""
    return get_node_history(node_id, hours)


def analyze_temporal_trends(hours: int = 24) -> Dict[str, Any]:
    """Analiza tendencias temporales del grafo en las últimas N horas."""
    snapshots = get_recent_snapshots(hours)

    if len(snapshots) < 2:
        return {"error": "Insuficientes snapshots para análisis temporal", "snapshots_count": len(snapshots)}

    # Ordenar por timestamp ascendente
    snapshots_sorted = sorted(snapshots, key=lambda x: x["timestamp"])

    # Calcular tendencias
    node_counts = [s["node_count"] for s in snapshots_sorted]
    edge_counts = [s["edge_count"] for s in snapshots_sorted]

    node_trend = (
        "increasing"
        if node_counts[-1] > node_counts[0]
        else "decreasing"
        if node_counts[-1] < node_counts[0]
        else "stable"
    )
    edge_trend = (
        "increasing"
        if edge_counts[-1] > edge_counts[0]
        else "decreasing"
        if edge_counts[-1] < edge_counts[0]
        else "stable"
    )

    # Detectar nodos emergentes (nuevos en el último snapshot)
    latest_graph = snapshots_sorted[-1]["graph_data"]
    previous_graph = snapshots_sorted[-2]["graph_data"] if len(snapshots_sorted) >= 2 else latest_graph

    latest_nodes = {n["id"] for n in latest_graph.get("nodes", [])}
    previous_nodes = {n["id"] for n in previous_graph.get("nodes", [])}

    emerging_nodes = latest_nodes - previous_nodes

    return {
        "period_hours": hours,
        "snapshots_analyzed": len(snapshots_sorted),
        "node_trend": node_trend,
        "edge_trend": edge_trend,
        "node_delta": node_counts[-1] - node_counts[0],
        "edge_delta": edge_counts[-1] - edge_counts[0],
        "emerging_nodes": list(emerging_nodes)[:10],  # Top 10 nuevos nodos
        "first_snapshot": snapshots_sorted[0]["timestamp"],
        "last_snapshot": snapshots_sorted[-1]["timestamp"],
    }


def compare_graph_periods(hours_ago: int = 24) -> Dict[str, Any]:
    """Compara el grafo actual con uno de hace N horas."""
    latest = get_latest_snapshot()
    if not latest:
        return {"error": "No hay snapshots disponibles"}

    (datetime.now() - timedelta(hours=hours_ago)).isoformat()

    snapshots = get_recent_snapshots(hours_ago + 1)  # +1 para incluir el periodo completo

    # Buscar snapshot más cercano al cutoff time
    target_snapshot = None
    for snap in sorted(
        snapshots,
        key=lambda x: abs(datetime.fromisoformat(x["timestamp"]) - datetime.now() + timedelta(hours=hours_ago)),
    ):
        if datetime.fromisoformat(snap["timestamp"]) <= datetime.now() - timedelta(hours=hours_ago):
            target_snapshot = snap
            break

    if not target_snapshot:
        return {"error": "No se encontró snapshot del periodo especificado"}

    # Comparar usando la función de graph_database
    comparison = compare_snapshots(target_snapshot["id"], latest["id"])

    return {
        "period_hours": hours_ago,
        "comparison": comparison,
        "earlier_timestamp": target_snapshot["timestamp"],
        "current_timestamp": latest["timestamp"],
    }


def filter_graph_by_entity_type(graph: Dict, entity_types: List[str] = None) -> Dict:
    """Filtra el grafo por tipo de entidad (persons, organizations, locations)."""
    if not entity_types:
        return graph

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Filtrar nodos por tipo
    filtered_node_ids = {n["id"] for n in nodes if n.get("group") in entity_types}

    # Filtrar aristas para mantener solo conexiones entre nodos filtrados
    filtered_edges = [e for e in edges if e["from"] in filtered_node_ids and e["to"] in filtered_node_ids]

    # Filtrar nodos
    filtered_nodes = [n for n in nodes if n["id"] in filtered_node_ids]

    return {
        "nodes": filtered_nodes,
        "edges": filtered_edges,
        "metrics": graph.get("metrics", {}),
        "communities": graph.get("communities", {}),
        "entity_mentions": graph.get("entity_mentions", {}),
        "layouts": graph.get("layouts", {}),
    }


def filter_graph_by_sentiment(graph: Dict, sentiments: List[str] = None) -> Dict:
    """Filtra el grafo por sentimiento (positive, negative, neutral)."""
    if not sentiments:
        return graph

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Filtrar nodos por sentimiento
    filtered_node_ids = {n["id"] for n in nodes if n.get("sentiment") in sentiments}

    # Filtrar aristas
    filtered_edges = [e for e in edges if e["from"] in filtered_node_ids and e["to"] in filtered_node_ids]

    # Filtrar nodos
    filtered_nodes = [n for n in nodes if n["id"] in filtered_node_ids]

    return {
        "nodes": filtered_nodes,
        "edges": filtered_edges,
        "metrics": graph.get("metrics", {}),
        "communities": graph.get("communities", {}),
        "entity_mentions": graph.get("entity_mentions", {}),
        "layouts": graph.get("layouts", {}),
    }


def filter_graph_by_community(graph: Dict, community_ids: List[int] = None) -> Dict:
    """Filtra el grafo por ID de comunidad."""
    if not community_ids:
        return graph

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    communities = graph.get("communities", {})

    # Filtrar nodos por comunidad
    filtered_node_ids = {n["id"] for n in nodes if communities.get(n["id"]) in community_ids}

    # Filtrar aristas
    filtered_edges = [e for e in edges if e["from"] in filtered_node_ids and e["to"] in filtered_node_ids]

    # Filtrar nodos
    filtered_nodes = [n for n in nodes if n["id"] in filtered_node_ids]

    return {
        "nodes": filtered_nodes,
        "edges": filtered_edges,
        "metrics": graph.get("metrics", {}),
        "communities": graph.get("communities", {}),
        "entity_mentions": graph.get("entity_mentions", {}),
        "layouts": graph.get("layouts", {}),
    }


def search_and_highlight_entity(graph: Dict, search_query: str) -> Dict:
    """Busca una entidad y resalta sus conexiones en el grafo."""
    if not search_query:
        return graph

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    search_lower = search_query.lower()

    # Buscar nodos que coincidan
    matched_node_ids = {
        n["id"] for n in nodes if search_lower in n["id"].lower() or search_lower in n.get("label", "").lower()
    }

    if not matched_node_ids:
        return graph

    # Encontrar todos los nodos conectados (vecinos)
    connected_node_ids = set()
    for edge in edges:
        if edge["from"] in matched_node_ids:
            connected_node_ids.add(edge["to"])
        if edge["to"] in matched_node_ids:
            connected_node_ids.add(edge["from"])

    # Marcar nodos: matched (rojo), connected (amarillo), otros (gris)
    for node in nodes:
        if node["id"] in matched_node_ids:
            node["highlight"] = "matched"
            node["color"] = "#FF2D55"
        elif node["id"] in connected_node_ids:
            node["highlight"] = "connected"
            node["color"] = "#FFCC00"
        else:
            node["highlight"] = "none"
            node["color"] = "#888888"

    # Marcar aristas conectadas
    for edge in edges:
        if edge["from"] in matched_node_ids or edge["to"] in matched_node_ids:
            edge["highlight"] = True
            edge["color"] = "#FF2D55"
        else:
            edge["highlight"] = False
            edge["color"] = "#3c4155"

    return {
        "nodes": nodes,
        "edges": edges,
        "metrics": graph.get("metrics", {}),
        "communities": graph.get("communities", {}),
        "entity_mentions": graph.get("entity_mentions", {}),
        "layouts": graph.get("layouts", {}),
        "search_query": search_query,
        "matched_nodes": list(matched_node_ids),
    }


def filter_graph_by_time_range(graph: Dict, entries: List[Dict], hours: int = 24) -> Dict:
    """Filtra el grafo por rango de tiempo usando las entradas originales."""
    if hours <= 0:
        return graph

    cutoff_time = datetime.now() - timedelta(hours=hours)

    # Filtrar entradas por tiempo
    filtered_entries = []
    for entry in entries:
        published = entry.get("published")
        if published:
            try:
                entry_time = datetime.fromisoformat(published.replace("Z", "+00:00"))
                if entry_time >= cutoff_time:
                    filtered_entries.append(entry)
            except Exception:
                continue

    # Reconstruir grafo con entradas filtradas
    if not filtered_entries:
        return {"nodes": [], "edges": [], "metrics": {}, "communities": {}, "entity_mentions": {}, "layouts": {}}

    return _build_graph(filtered_entries, use_ai=False)


def get_graph_timeline(hours: int = 24, interval_hours: int = 1) -> List[Dict]:
    """Obtiene snapshots del grafo para crear un timeline animado de evolución."""
    snapshots = get_recent_snapshots(hours)

    if len(snapshots) < 2:
        return []

    # Agrupar snapshots por intervalos de tiempo
    timeline = []
    current_time = datetime.now()

    for i in range(0, hours, interval_hours):
        interval_start = current_time - timedelta(hours=i + interval_hours)
        interval_end = current_time - timedelta(hours=i)

        # Encontrar snapshot más cercano en este intervalo
        interval_snapshots = [
            s for s in snapshots if interval_start <= datetime.fromisoformat(s["timestamp"]) < interval_end
        ]

        if interval_snapshots:
            # Usar el snapshot más reciente del intervalo
            latest_in_interval = max(interval_snapshots, key=lambda x: x["timestamp"])
            timeline.append(
                {
                    "timestamp": latest_in_interval["timestamp"],
                    "node_count": latest_in_interval["node_count"],
                    "edge_count": latest_in_interval["edge_count"],
                    "graph_data": latest_in_interval["graph_data"],
                    "interval_start": interval_start.isoformat(),
                    "interval_end": interval_end.isoformat(),
                }
            )

    return sorted(timeline, key=lambda x: x["timestamp"])


def get_geographic_locations(graph: Dict) -> List[Dict]:
    """Extrae ubicaciones del grafo para visualización en mapa geográfico."""
    nodes = graph.get("nodes", [])

    locations = []
    for node in nodes:
        if node.get("group") == "locations":
            locations.append(
                {
                    "id": node["id"],
                    "label": node.get("label", node["id"]),
                    "value": node.get("value", 1),
                    "sentiment": node.get("sentiment", "neutral"),
                    "community": node.get("community", 0),
                }
            )

    return locations


def calculate_activity_heatmap(graph: Dict) -> Dict[str, float]:
    """Calcula un heatmap de actividad basado en frecuencia de mención y centralidad."""
    nodes = graph.get("nodes", [])
    metrics = graph.get("metrics", {})
    entity_mentions = graph.get("entity_mentions", {})

    heatmap = {}

    for node in nodes:
        node_id = node["id"]

        # Combinar métricas para calcular actividad
        mention_freq = entity_mentions.get(node_id, 0)
        pagerank = metrics.get(node_id, {}).get("pagerank", 0)
        betweenness = metrics.get(node_id, {}).get("betweenness_centrality", 0)

        # Puntuación de actividad (0-1)
        activity_score = (
            min(mention_freq / 10, 1) * 0.4  # Frecuencia de mención (40%)
            + pagerank * 0.3  # PageRank (30%)
            + betweenness * 0.3  # Betweenness (30%)
        )

        heatmap[node_id] = round(activity_score, 3)

    return heatmap


def get_top_nodes(graph: Dict, metric: str = "pagerank", top_n: int = 5) -> List[Dict]:
    """Obtiene los top N nodos según una métrica específica."""
    nodes = graph.get("nodes", [])
    metrics = graph.get("metrics", {})

    # Ordenar nodos por la métrica especificada
    sorted_nodes = sorted(nodes, key=lambda n: metrics.get(n["id"], {}).get(metric, 0), reverse=True)

    top_nodes = []
    for node in sorted_nodes[:top_n]:
        node_metrics = metrics.get(node["id"], {})
        top_nodes.append(
            {
                "id": node["id"],
                "label": node.get("label", node["id"]),
                "group": node.get("group", ""),
                "value": node.get("value", 1),
                "sentiment": node.get("sentiment", "neutral"),
                "community": node.get("community", 0),
                "metrics": {
                    "pagerank": node_metrics.get("pagerank", 0),
                    "betweenness_centrality": node_metrics.get("betweenness_centrality", 0),
                    "degree_centrality": node_metrics.get("degree_centrality", 0),
                    "closeness_centrality": node_metrics.get("closeness_centrality", 0),
                    "eigenvector_centrality": node_metrics.get("eigenvector_centrality", 0),
                },
            }
        )

    return top_nodes


def get_realtime_metrics(graph: Dict) -> Dict[str, Any]:
    """Obtiene métricas en tiempo real del grafo."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    communities = graph.get("communities", {})
    metrics = graph.get("metrics", {})
    graph.get("entity_mentions", {})

    # Contar nodos por tipo
    nodes_by_type = {"persons": 0, "organizations": 0, "locations": 0}
    for node in nodes:
        group = node.get("group", "")
        if group in nodes_by_type:
            nodes_by_type[group] += 1

    # Contar nodos por sentimiento
    nodes_by_sentiment = {"positive": 0, "negative": 0, "neutral": 0}
    for node in nodes:
        sentiment = node.get("sentiment", "neutral")
        if sentiment in nodes_by_sentiment:
            nodes_by_sentiment[sentiment] += 1

    # Contar comunidades
    community_count = len(set(communities.values())) if communities else 0

    # Top nodos por diferentes métricas
    top_by_pagerank = get_top_nodes(graph, "pagerank", 5)
    top_by_betweenness = get_top_nodes(graph, "betweenness_centrality", 5)
    top_by_degree = get_top_nodes(graph, "degree_centrality", 5)

    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "nodes_by_type": nodes_by_type,
        "nodes_by_sentiment": nodes_by_sentiment,
        "community_count": community_count,
        "top_pagerank": top_by_pagerank,
        "top_betweenness": top_by_betweenness,
        "top_degree": top_by_degree,
        "avg_pagerank": sum(metrics.get(n["id"], {}).get("pagerank", 0) for n in nodes) / len(nodes) if nodes else 0,
        "avg_betweenness": sum(metrics.get(n["id"], {}).get("betweenness_centrality", 0) for n in nodes) / len(nodes)
        if nodes
        else 0,
    }


def get_sentiment_evolution(node_id: str, hours: int = 168) -> List[Dict]:
    """Obtiene la evolución del sentimiento de una entidad en el tiempo."""
    history = get_node_history(node_id, hours)

    if not history:
        return []

    # Calcular sentimiento promedio por snapshot
    evolution = []
    for entry in history:
        # Asumimos que el historial ya tiene datos de sentimiento
        evolution.append(
            {
                "timestamp": entry["timestamp"],
                "degree_centrality": entry.get("degree_centrality", 0),
                "betweenness_centrality": entry.get("betweenness_centrality", 0),
                "pagerank": entry.get("pagerank", 0),
            }
        )

    return sorted(evolution, key=lambda x: x["timestamp"])


def compare_periods_side_by_side(hours_ago_1: int = 24, hours_ago_2: int = 48) -> Dict[str, Any]:
    """Compara dos periodos de tiempo para vista lado a lado."""
    latest = get_latest_snapshot()
    if not latest:
        return {"error": "No hay snapshots disponibles"}

    # Obtener snapshot del periodo 1
    cutoff_1 = datetime.now() - timedelta(hours=hours_ago_1)
    snapshots_1 = get_recent_snapshots(hours_ago_1 + 1)
    period_1 = None
    for snap in sorted(snapshots_1, key=lambda x: abs(datetime.fromisoformat(x["timestamp"]) - cutoff_1)):
        if datetime.fromisoformat(snap["timestamp"]) <= cutoff_1:
            period_1 = snap
            break

    # Obtener snapshot del periodo 2
    cutoff_2 = datetime.now() - timedelta(hours=hours_ago_2)
    snapshots_2 = get_recent_snapshots(hours_ago_2 + 1)
    period_2 = None
    for snap in sorted(snapshots_2, key=lambda x: abs(datetime.fromisoformat(x["timestamp"]) - cutoff_2)):
        if datetime.fromisoformat(snap["timestamp"]) <= cutoff_2:
            period_2 = snap
            break

    if not period_1 or not period_2:
        return {"error": "No se encontraron snapshots de los periodos especificados"}

    # Calcular métricas para cada periodo
    metrics_1 = get_realtime_metrics(period_1["graph_data"])
    metrics_2 = get_realtime_metrics(period_2["graph_data"])

    return {
        "period_1": {"timestamp": period_1["timestamp"], "hours_ago": hours_ago_1, "metrics": metrics_1},
        "period_2": {"timestamp": period_2["timestamp"], "hours_ago": hours_ago_2, "metrics": metrics_2},
        "comparison": {
            "node_delta": metrics_1["total_nodes"] - metrics_2["total_nodes"],
            "edge_delta": metrics_1["total_edges"] - metrics_2["total_edges"],
            "community_delta": metrics_1["community_count"] - metrics_2["community_count"],
        },
    }


def detect_bridge_nodes(graph: Dict) -> List[Dict]:
    """Detecta nodos puente que conectan diferentes comunidades (influencia cruzada)."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    communities = graph.get("communities", {})
    metrics = graph.get("metrics", {})

    if not communities:
        return []

    # Construir grafo de NetworkX para análisis
    g = nx.Graph()
    for node in nodes:
        g.add_node(node["id"], community=communities.get(node["id"], 0))
    for edge in edges:
        g.add_edge(edge["from"], edge["to"])

    # Detectar nodos puente (aristas que si se eliminan desconectan comunidades)
    bridge_edges = list(nx.bridges(g))

    # Nodos involucrados en aristas puente
    bridge_node_ids = set()
    for u, v in bridge_edges:
        bridge_node_ids.add(u)
        bridge_node_ids.add(v)

    # Calcular betweenness centrality para nodos puente
    bridge_nodes = []
    for node_id in bridge_node_ids:
        node_data = next((n for n in nodes if n["id"] == node_id), None)
        if node_data:
            node_metrics = metrics.get(node_id, {})
            bridge_nodes.append(
                {
                    "id": node_id,
                    "label": node_data.get("label", node_id),
                    "group": node_data.get("group", ""),
                    "community": communities.get(node_id, 0),
                    "betweenness_centrality": node_metrics.get("betweenness_centrality", 0),
                    "pagerank": node_metrics.get("pagerank", 0),
                    "bridge_connections": len([e for e in bridge_edges if node_id in e]),
                }
            )

    # Ordenar por betweenness centrality
    bridge_nodes.sort(key=lambda x: x["betweenness_centrality"], reverse=True)

    return bridge_nodes


def detect_significant_changes(hours: int = 24) -> Dict[str, Any]:
    """Detecta cambios significativos en el grafo y genera alertas."""
    if not ENABLE_ALERTS:
        return {"alerts_enabled": False, "message": "Sistema de alertas deshabilitado"}

    snapshots = get_recent_snapshots(hours)

    if len(snapshots) < 2:
        return {"error": "Insuficientes snapshots para detección de cambios", "snapshots_count": len(snapshots)}

    # Ordenar por timestamp
    snapshots_sorted = sorted(snapshots, key=lambda x: x["timestamp"])

    earlier = snapshots_sorted[0]
    latest = snapshots_sorted[-1]

    alerts = []

    # Detectar crecimiento anómalo de nodos
    node_delta = latest["node_count"] - earlier["node_count"]
    node_growth_rate = node_delta / earlier["node_count"] if earlier["node_count"] > 0 else 0

    if node_growth_rate > ALERT_THRESHOLDS["node_growth_rate"]:
        alerts.append(
            {
                "type": "node_growth",
                "severity": "high" if node_growth_rate > 1.0 else "medium",
                "message": f"Crecimiento anómalo de nodos: {node_delta} nuevos nodos ({node_growth_rate:.1%})",
                "value": node_growth_rate,
                "threshold": ALERT_THRESHOLDS["node_growth_rate"],
            }
        )

    # Detectar crecimiento anómalo de aristas
    edge_delta = latest["edge_count"] - earlier["edge_count"]
    edge_growth_rate = edge_delta / earlier["edge_count"] if earlier["edge_count"] > 0 else 0

    if edge_growth_rate > ALERT_THRESHOLDS["edge_growth_rate"]:
        alerts.append(
            {
                "type": "edge_growth",
                "severity": "high" if edge_growth_rate > 1.0 else "medium",
                "message": f"Crecimiento anómalo de aristas: {edge_delta} nuevas aristas ({edge_growth_rate:.1%})",
                "value": edge_growth_rate,
                "threshold": ALERT_THRESHOLDS["edge_growth_rate"],
            }
        )

    # Detectar picos en centralidad de nodos existentes
    earlier_metrics = earlier.get("metrics_summary", {})
    latest_metrics = latest.get("metrics_summary", {})

    centrality_spikes = []
    for node_id in latest_metrics:
        if node_id in earlier_metrics:
            earlier_bc = earlier_metrics[node_id].get("betweenness_centrality", 0)
            latest_bc = latest_metrics[node_id].get("betweenness_centrality", 0)

            if earlier_bc > 0:
                bc_change = (latest_bc - earlier_bc) / earlier_bc
                if bc_change > ALERT_THRESHOLDS["centrality_spike"]:
                    centrality_spikes.append(
                        {"node_id": node_id, "change": bc_change, "earlier": earlier_bc, "latest": latest_bc}
                    )

    if centrality_spikes:
        alerts.append(
            {
                "type": "centrality_spike",
                "severity": "medium",
                "message": f"{len(centrality_spikes)} nodos con picos de centralidad",
                "nodes": centrality_spikes[:5],  # Top 5
            }
        )

    # Detectar nuevos nodos críticos (alta centralidad)
    latest_graph = latest["graph_data"]
    earlier_graph = earlier["graph_data"]

    latest_nodes = {n["id"]: n for n in latest_graph.get("nodes", [])}
    earlier_nodes = {n["id"]: n for n in earlier_graph.get("nodes", [])}

    new_critical_nodes = []
    for node_id, node in latest_nodes.items():
        if node_id not in earlier_nodes:
            pagerank = node.get("pagerank", 0)
            if pagerank > 0.1:  # Umbral arbitrario para "crítico"
                new_critical_nodes.append(
                    {"node_id": node_id, "pagerank": pagerank, "label": node.get("label", node_id)}
                )

    if len(new_critical_nodes) >= ALERT_THRESHOLDS["new_critical_nodes"]:
        alerts.append(
            {
                "type": "new_critical_nodes",
                "severity": "high",
                "message": f"{len(new_critical_nodes)} nuevos nodos con alta centralidad",
                "nodes": new_critical_nodes,
            }
        )

    return {
        "period_hours": hours,
        "snapshots_compared": len(snapshots_sorted),
        "earlier_timestamp": earlier["timestamp"],
        "latest_timestamp": latest["timestamp"],
        "alerts": alerts,
        "alert_count": len(alerts),
        "summary": {
            "node_delta": node_delta,
            "node_growth_rate": round(node_growth_rate, 3),
            "edge_delta": edge_delta,
            "edge_growth_rate": round(edge_growth_rate, 3),
        },
    }


if __name__ == "__main__":
    test = [
        {
            "title": "Maduro se reúne con la FANB en Caracas",
            "summary": "El presidente Maduro y la FANB...",
            "source": "AVN",
        },
        {"title": "Machado denuncia fraude en el CNE", "summary": "María Corina Machado...", "source": "Runrun.es"},
        {
            "title": "PDVSA anuncia nueva producción en el Zulia",
            "summary": "PDVSA en Maracaibo...",
            "source": "El Nacional",
        },
    ]
    r = get_social_graph(test, use_ai=False)
    print(f"Graph: {r['count']} nodos, {r['edges']} aristas (método: {r['extraction_method']})")
    print(json.dumps(r["graph"], indent=2))
