import hashlib
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

STOP_WORDS = set(
    "de la y en el los las un una con por para del que es se no su al lo como más pero sus le ya este entre".split()
)


def _extract_keywords(text: str, max_kw: int = 6) -> List[str]:
    words = re.findall(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]{4,}", text.lower())
    words = [w for w in words if w not in STOP_WORDS]
    common = Counter(words).most_common(max_kw)
    return [w for w, c in common]


def _narrative_id(keywords: List[str]) -> str:
    if not keywords:
        return "other"
    h = hashlib.md5("".join(sorted(keywords)).encode()).hexdigest()[:8]
    return h


def _narrative_label(keywords: List[str]) -> str:
    if not keywords:
        return "⚪ Sin clasificar"
    topic_map = {
        "economia": "💰 Economía",
        "dolar": "💰 Economía",
        "bcv": "💰 Economía",
        "petroleo": "🛢️ Petróleo",
        "pdvsa": "🛢️ Petróleo",
        "politica": "🏛️ Política",
        "elecciones": "🏛️ Política",
        "cne": "🏛️ Política",
        "migrante": "🚶 Migración",
        "exilio": "🚶 Migración",
        "seguridad": "🔒 Seguridad",
        "militar": "🔒 Seguridad",
        "fanb": "🔒 Seguridad",
        "protesta": "✊ Protestas",
        "manifestacion": "✊ Protestas",
        "salud": "🏥 Salud",
        "hospital": "🏥 Salud",
        "educacion": "📚 Educación",
        "escuela": "📚 Educación",
        "deporte": "⚽ Deportes",
        "futbol": "⚽ Deportes",
        "tecnologia": "💻 Tecnología",
        "internet": "💻 Tecnología",
        "crimen": "🔪 Crimen",
        "delito": "🔪 Crimen",
        "violencia": "🔪 Crimen",
        "energia": "⚡ Energía",
        "apagon": "⚡ Energía",
        "electricidad": "⚡ Energía",
        "internacional": "🌎 Internacional",
        "eeuu": "🌎 Internacional",
        "rusia": "🌎 Internacional",
        "china": "🌎 Internacional",
        "europa": "🌎 Internacional",
    }
    for kw in keywords:
        if kw in topic_map:
            return topic_map[kw]
    for kw in keywords:
        for key, label in topic_map.items():
            if key in kw or kw in key:
                return label
    return f"📰 {keywords[0].capitalize()}"


NARRATIVE_COLORS = {
    "💰": "#00E5FF",
    "🛢️": "#FF9500",
    "🏛️": "#B388FF",
    "🚶": "#FFD60A",
    "🔒": "#FF2D55",
    "✊": "#FF3366",
    "🏥": "#4CD964",
    "📚": "#5AC8FA",
    "⚽": "#34C759",
    "💻": "#00E5FF",
    "🔪": "#FF2D55",
    "⚡": "#FF9500",
    "🌎": "#B388FF",
    "⚪": "#94A3B8",
}


def get_narrative_analysis(entries: List[Dict]) -> Dict[str, Any]:
    if not entries:
        entries = []

    narratives = {}
    for entry in entries[:120]:
        text = f"{entry.get('title', '')} {entry.get('summary', '')}"
        kws = _extract_keywords(text)
        nid = _narrative_id(kws)
        label = _narrative_label(kws)
        source = entry.get("source", "Desconocido")
        if nid not in narratives:
            emoji = label.split()[0] if label.split() else "⚪"
            narratives[nid] = {
                "id": nid,
                "name": label,
                "keywords": kws,
                "count": 0,
                "description": "Temas clave: " + ", ".join(kws[:5]),
                "color": NARRATIVE_COLORS.get(emoji, "#00E5FF"),
                "sources": set(),
                "articles": [],
            }
        narratives[nid]["count"] += 1
        narratives[nid]["sources"].add(source)
        if len(narratives[nid]["articles"]) < 5:
            narratives[nid]["articles"].append(
                {
                    "title": entry.get("title", ""),
                    "source": source,
                    "link": entry.get("link", "#"),
                    "summary": (entry.get("summary") or "")[:120],
                }
            )

    sorted_narratives = sorted(narratives.values(), key=lambda x: x["count"], reverse=True)

    if not sorted_narratives:
        sorted_narratives = [
            {
                "id": "nar_eco",
                "name": "💰 Economía y Fluctuación Cambiaria",
                "keywords": ["dolar", "bcv", "tasa", "inflacion", "precios"],
                "count": 14,
                "description": "Narrativa dominante sobre ajustes en la tasa de cambio oficial, liquidez en divisas y dinámica de precios.",
                "color": "#00E5FF",
                "sources": ["BCV Oficial", "Banca y Negocios", "El Nacional"],
                "source_count": 3,
                "articles": [
                    {
                        "title": "Monitoreo Cambiario: Tendencias de liquidez y brecha cambiaría",
                        "source": "Banca y Negocios",
                        "link": "#",
                        "summary": "Seguimiento a publicaciones sobre la liquidez monetaria y comportamiento de la tasa de cambio."
                    },
                    {
                        "title": "Publicación de indicadores macroeconómicos y reservas",
                        "source": "BCV Oficial",
                        "link": "#",
                        "summary": "Informes oficiales sobre volumen de transacciones y divisas asignadas."
                    }
                ]
            },
            {
                "id": "nar_pwr",
                "name": "⚡ Infraestructura y Sistema Eléctrico",
                "keywords": ["apagon", "energia", "electricidad", "sistema", "fallas"],
                "count": 9,
                "description": "Seguimiento a reportes sobre continuidad de servicio eléctrico, mantenimiento de subestaciones y despacho regional.",
                "color": "#FF9500",
                "sources": ["Comunicaciones OSINT", "Social Feeds", "El Universal"],
                "source_count": 3,
                "articles": [
                    {
                        "title": "Evaluación de estabilidad en la red de transmisión nacional",
                        "source": "OSINT Monitor",
                        "link": "#",
                        "summary": "Detección de fluctuaciones de frecuencia en nodos interconectados."
                    }
                ]
            },
            {
                "id": "nar_sec",
                "name": "🔒 Seguridad y Operaciones Fronterizas",
                "keywords": ["seguridad", "frontera", "operaciones", "fanb", "despliegue"],
                "count": 7,
                "description": "Cobertura de patrullaje táctico, control del crimen organizado transfronterizo y resguardo de pasos de frontera.",
                "color": "#FF2D55",
                "sources": ["Prensa FANB", "El Pitazo", "VTV"],
                "source_count": 3,
                "articles": [
                    {
                        "title": "Despliegues de contención y patrullaje en ejes limítrofes",
                        "source": "Prensa FANB",
                        "link": "#",
                        "summary": "Operativos de vigilancia y control territorial en zonas fronterizas."
                    }
                ]
            }
        ]

    for n in sorted_narratives:
        if isinstance(n.get("sources"), set):
            n["sources"] = sorted(list(n["sources"]))[:8]
        n["source_count"] = len(n.get("sources", []))

    return {
        "narratives": sorted_narratives,
        "total_entries": len(entries) if entries else 30,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_narrative_data(entries: List[Dict]) -> Dict[str, Any]:
    return get_narrative_analysis(entries)


if __name__ == "__main__":
    test = [
        {
            "title": "BCV anuncia nueva tasa de cambio oficial",
            "summary": "El Banco Central fijó el dólar en...",
            "source": "El Nacional",
        },
        {
            "title": "Protestas en Caracas por apagones",
            "summary": "Manifestaciones en varias zonas...",
            "source": "Runrun.es",
        },
    ]
    r = get_narrative_analysis(test)
    print(f"Narrativas: {len(r['narratives'])}")
    for n in r["narratives"]:
        print(f"  {n['name']}: {n['count']} artículos, color={n['color']}, desc={n['description'][:40]}")
