"""
REPORT GENERATOR (Módulo Exportable de Generación de Informes por IA)
====================================================================
Genera informes analíticos, evaluación de riesgos en formato JSON estructurado
y debates sintéticos entre múltiples agentes IA.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from ai_engine import ask_ai

logger = logging.getLogger("ReportGenerator")

# Prompts de Sistema
SITREP_SYSTEM_PROMPT = (
    "Eres un analista senior de inteligencia operando en un centro C4I. "
    "Analiza la información provista y genera una evaluación táctica estructurada. "
    "Responde EXCLUSIVAMENTE con un JSON válido que contenga la siguiente estructura: "
    '{"actores": ["actor1", "actor2"], "nivel_amenaza": "CRÍTICA|ALTA|MEDIA|BAJA", "resumen_ejecutivo": "2-3 oraciones", "recomendaciones": ["rec1", "rec2"]}'
)

DEBATE_AGENTS = {
    "Analista Táctico ( Neutral )": "Analiza los hechos puros, verificación fáctica de fuentes y logística.",
    "Analista Geopolítico ( Perspectiva Externa )": "Evalúa implicaciones económicas, diplomáticas y sanciones.",
    "Analista de Ciberseguridad & Redes": "Evalúa vectores ciber, narrativa digital y señales.",
}


async def generar_informe_sitrep(titulo: str, contenido: str, fuente: str = "OSINT") -> Dict[str, Any]:
    """Procesa una sola noticia o evento y genera un informe estructurado JSON."""
    prompt = f"TÍTULO: {titulo}\nFUENTE: {fuente}\nCONTENIDO: {contenido[:2000]}"
    raw_response = await ask_ai(
        prompt=prompt,
        system_prompt=SITREP_SYSTEM_PROMPT,
        json_mode=True,
        temperature=0.2,
        max_tokens=600,
    )

    if not raw_response:
        return {
            "actores": ["No identificados"],
            "nivel_amenaza": "INDETERMINADO",
            "resumen_ejecutivo": "No se pudo procesar la consulta por falta de conexión a la IA.",
            "recomendaciones": [],
        }

    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        return {
            "actores": ["Error de formato"],
            "nivel_amenaza": "MEDIA",
            "resumen_ejecutivo": raw_response,
            "recomendaciones": [],
        }


async def generar_informe_masivo(entradas: List[Dict[str, str]], limite_concurrencia: int = 4) -> List[Dict[str, Any]]:
    """Procesa múltiples noticias en paralelo con control de concurrencia."""
    semaphore = asyncio.Semaphore(limite_concurrencia)
    resultados = []

    async def _worker(item: Dict[str, str]):
        async with semaphore:
            res = await generar_informe_sitrep(
                titulo=item.get("titulo", item.get("title", "")),
                contenido=item.get("contenido", item.get("summary", "")),
                fuente=item.get("fuente", item.get("source", "N/A")),
            )
            item_copia = dict(item)
            item_copia["informe_ia"] = res
            return item_copia

    tareas = [_worker(entry) for entry in entradas]
    resultados = await asyncio.gather(*tareas, return_exceptions=True)
    return [r for r in resultados if isinstance(r, dict)]


async def generar_debate_multiagente(noticias: List[Dict[str, str]]) -> Dict[str, Any]:
    """Genera un debate sintético entre agentes especializados sobre un conjunto de noticias."""
    contexto_noticias = "\n".join([f"- {n.get('titulo', n.get('title'))}: {n.get('contenido', n.get('summary'))[:150]}" for n in noticias[:10]])
    posiciones = {}

    for agente, enfoque in DEBATE_AGENTS.items():
        prompt = f"Noticias recientes:\n{contexto_noticias}\n\nComo {agente} ({enfoque}), proporciona tu análisis en un párrafo directo (máximo 120 palabras)."
        respuesta = await ask_ai(prompt=prompt, temperature=0.4, max_tokens=300)
        posiciones[agente] = respuesta or "Sin respuesta."

    # Consenso final
    prompt_consenso = f"Basado en las siguientes perspectivas:\n{json.dumps(posiciones, ensure_ascii=False, indent=2)}\n\nGenera una conclusión de consenso ejecutivo en 3 líneas."
    consenso = await ask_ai(prompt=prompt_consenso, temperature=0.2, max_tokens=250)

    return {
        "agentes": posiciones,
        "consenso_ejecutivo": consenso or "Consenso no disponible.",
    }
