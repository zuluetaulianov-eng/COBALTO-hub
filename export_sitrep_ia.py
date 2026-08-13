import asyncio
import json
import logging

from openai import APIError, APITimeoutError
from openai import OpenAI as Groq

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres un analista de inteligencia de fuentes abiertas (OSINT) del sistema COBALTO C4I. "
    "Analiza la siguiente entrada de inteligencia y genera un informe estructurado. "
    "Debes devolver tu análisis EXCLUSIVAMENTE en formato JSON válido con la siguiente estructura: "
    '{"actores": ["actor1", "actor2"], "amenaza": "Alta|Media|Baja|Critica", "analisis": "Texto analítico en tono militar formal (2-4 oraciones)"}. '
    "No incluyas nada fuera del JSON."
)


class SitrepIAError(Exception):
    pass


def _get_groq_client():
    from ai_core import _groq_pool
    if _groq_pool and len(_groq_pool) > 0:
        return Groq(api_key=_groq_pool[0], base_url="https://integrate.api.nvidia.com/v1")
    return None


async def analizar_entrada_ia(title: str, summary: str, source: str) -> dict:
    import config
    from ai_local import LOCAL_AI_ENABLED, query_local_llm

    prompt_text = f"Titulo: {title}\nFuente: {source}\nContenido: {summary[:2000]}"
    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt_text}"

    # Si se prefiere IA local o no hay cliente externo
    client = _get_groq_client()
    if getattr(config, "PREFER_LOCAL_AI", True) or not client:
        if LOCAL_AI_ENABLED:
            try:
                content = await query_local_llm(full_prompt, max_tokens=500, temperature=0.3)
                if content:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start != -1 and end > start:
                        result = json.loads(content[start:end])
                        return {
                            "actores": result.get("actores", ["N/A"]),
                            "amenaza": str(result.get("amenaza", "Desconocida")),
                            "analisis": str(result.get("analisis", "")),
                        }
                    return {"actores": ["N/A"], "amenaza": "Desconocida", "analisis": content}
            except Exception as ex:
                logger.warning(f"Fallo IA local en sitrep: {ex}")

    if not client:
        return {"actores": ["N/A"], "amenaza": "Desconocida", "analisis": "IA no disponible. Analisis omitido."}

    try:
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model=config.AI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_text},
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
        )
        content = response.choices[0].message.content.strip()
        try:
            result = json.loads(content)
            return {
                "actores": result.get("actores", ["N/A"]),
                "amenaza": str(result.get("amenaza", "Desconocida")),
                "analisis": str(result.get("analisis", "")),
            }
        except json.JSONDecodeError:
            logger.warning("IA no devolvió JSON válido, usando fallback")
            return {"actores": ["N/A"], "amenaza": "Desconocida", "analisis": content}
    except APITimeoutError:
        logger.error("Timeout en IA Groq")
        return {"actores": ["N/A"], "amenaza": "Desconocida", "analisis": "Error: Timeout en IA."}
    except APIError as e:
        logger.error(f"Error API Groq: {e}")
        return {"actores": ["N/A"], "amenaza": "Desconocida", "analisis": f"Error IA: {str(e)[:100]}."}


async def analizar_entradas_masivo(entries: list) -> list:
    semaphore = asyncio.Semaphore(3)
    enriched = []

    async def _process_one(entry: dict):
        async with semaphore:
            analysis = await analizar_entrada_ia(
                str(entry.get("title", entry.get("titulo", ""))),
                str(entry.get("summary", entry.get("resumen", entry.get("texto", "")))),
                str(entry.get("source", entry.get("fuente", ""))),
            )
            enriched_entry = dict(entry)
            enriched_entry["analysis"] = analysis
            return enriched_entry

    tasks = [_process_one(e) for e in entries[:25]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            continue
        enriched.append(r)

    return enriched
