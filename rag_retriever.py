"""rag_retriever.py - Motor de Recuperación de Contexto (RAG Bajo Demanda).

Extrae y clasifica los documentos más relevantes de la base de datos local y del
contexto activo para alimentar al modelo LLM local (Ollama) sin saturar la GPU.
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _extraer_palabras_clave(texto: str) -> List[str]:
    """Extrae palabras clave de búsqueda ignorando stopwords comunes."""
    stopwords = {
        "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas",
        "y", "e", "o", "u", "en", "con", "sin", "por", "para", "sobre", "tras",
        "que", "que", "como", "cual", "cuales", "donde", "cuando", "quien",
        "dime", "dame", "analiza", "buscar", "busca", "sobre", "esta", "este",
        "estos", "estas", "hay", "hubo", "reporte", "noticias", "noticia",
    }
    limpio = re.sub(r"[^\w\s]", " ", texto.lower())
    tokens = limpio.split()
    return [t for t in tokens if len(t) > 2 and t not in stopwords]


def _calcular_score_relevancia(entry: dict, palabras_clave: List[str]) -> float:
    """Calcula un puntaje de relevancia para una entrada en función de las palabras clave."""
    if not palabras_clave:
        return 0.0

    titulo = entry.get("title", "").lower()
    resumen = entry.get("summary", "").lower() + " " + entry.get("intro", "").lower()
    fuente = entry.get("source", "").lower()
    entidades = [str(e).lower() for e in entry.get("entities", [])]

    score = 0.0
    for kw in palabras_clave:
        if kw in titulo:
            score += 4.0
        if kw in entidades:
            score += 3.0
        if kw in resumen:
            score += 1.5
        if kw in fuente:
            score += 1.0

    return score


def retrieve_relevant_entries(
    query: str,
    entries: Optional[List[Dict]] = None,
    max_docs: int = 8,
) -> List[Dict]:
    """Busca y clasifica las entradas más relevantes para la pregunta del usuario.

    Revisa primero las entradas activas en RAM y complementa con la base histórica si es necesario.
    """
    if entries is None:
        entries = []

    palabras_clave = _extraer_palabras_clave(query)
    if not palabras_clave and entries:
        return entries[:max_docs]

    # Clasificar entradas proporcionadas
    scored_entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        sc = _calcular_score_relevancia(entry, palabras_clave)
        if sc > 0:
            scored_entries.append((sc, entry))

    scored_entries.sort(key=lambda x: x[0], reverse=True)
    resultados = [item[1] for item in scored_entries[:max_docs]]

    # Si se necesitan más resultados, consultar en almacenamiento histórico SQLite
    if len(resultados) < max_docs and palabras_clave:
        try:
            from historical_store import query_range
            busqueda_str = " ".join(palabras_clave[:3])
            res_hist = query_range(search=busqueda_str, limit=max_docs)
            hist_entries = res_hist.get("entries", [])
            for h in hist_entries:
                if len(resultados) >= max_docs:
                    break
                # Evitar duplicados
                eid = h.get("entry_id") or h.get("title")
                if not any((r.get("entry_id") or r.get("title")) == eid for r in resultados):
                    resultados.append(h)
        except Exception as ex:
            logger.debug(f"[RAG RETRIEVER] Consulta a almacenamiento histórico omitida: {ex}")

    # Fallback: si no hay coincidencias directas, devolver las entradas más recientes
    if not resultados and entries:
        return entries[:max_docs]

    return resultados[:max_docs]


def build_rag_prompt(query: str, docs: List[Dict]) -> str:
    """Construye un prompt de RAG estructurado y optimizado en tokens para Ollama."""
    bloques_docs = []
    for idx, doc in enumerate(docs, 1):
        titulo = doc.get("title") or doc.get("titulo") or "Sin título"
        fuente = doc.get("source") or doc.get("fuente") or "desconocido"
        contenido = doc.get("summary") or doc.get("intro") or doc.get("contenido") or ""
        url = doc.get("link") or doc.get("url") or ""
        bloque = f"[DOC {idx}] {titulo}\nFuente: {fuente} | URL: {url}\nContenido: {contenido[:350]}"
        bloques_docs.append(bloque)

    contexto_str = "\n\n".join(bloques_docs) if bloques_docs else "No se encontraron documentos específicos en la base de datos local."

    prompt = f"""Actúa como un Analista de Inteligencia Táctica para 'COBALTO HUB'.
Responde a la consulta del usuario basándote ÚNICAMENTE en los siguientes documentos recuperados de la base de datos local:

--- DOCUMENTOS DE CONTEXTO RECUPERADOS ---
{contexto_str}
--- FIN DE DOCUMENTOS ---

CONSULTA DEL USUARIO: {query}

INSTRUCCIONES:
1. Responde directamente de manera ejecutiva, clara y objetiva.
2. CITA los documentos correspondientes usando las etiquetas [DOC 1], [DOC 2], etc.
3. Si la información no se encuentra en los documentos recuperados, indícalo expresamente.
4. No uses lenguaje especulativo ni introducciones innecesarias."""

    return prompt


def format_clean_ingestion_prompt(raw_text: str) -> str:
    """Construye el prompt para limpiar, resumir e ingerir texto crudo en FTS5."""
    return f"""Eres un Agente de Ingesta y Limpieza de Datos Tácticos.
Tu trabajo es tomar el siguiente texto, corregir errores ortográficos si los hay, y estructurarlo para que sea indexado de manera óptima por el motor de búsqueda Full-Text de COBALTO HUB.

Debes devolver el resultado EXACTAMENTE con esta estructura, sin agregar saludos ni comentarios:

[TÍTULO SUGERIDO]
(Escribe un título corto descriptivo)

[RESUMEN SEMÁNTICO]
(Escribe un resumen de 2 o 3 líneas del contenido)

[CONTENIDO LIMPIO]
(El texto corregido y bien formateado)

--- TEXTO DE ENTRADA ---
{raw_text}
------------------------"""

