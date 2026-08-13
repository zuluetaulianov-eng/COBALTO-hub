import asyncio
import json
import logging
from typing import Any, Dict

from groq import APIError, APITimeoutError, Groq

from backend.config import settings

logger = logging.getLogger("cobalto.groq")

groq_client = Groq(
    api_key=settings.groq_api_key,
    timeout=settings.groq_timeout,
)

_semaphore = asyncio.Semaphore(3)

SYSTEM_PROMPT = (
    "Eres un analista de inteligencia de fuentes abiertas (OSINT). "
    "Analiza la siguiente novedad de patrullaje digital. "
    "Debes devolver tu análisis EXCLUSIVAMENTE en formato JSON válido con la siguiente estructura: "
    '{"actores": ["actor1", "actor2"], "amenaza": "Alta/Media/Baja", "analisis": "tu texto en tono militar formal"}. '
    "No incluyas nada fuera del JSON."
)


class GroqAnalysisError(Exception):
    pass


async def obtener_analisis_ia(fecha: str, texto: str, descripciones_imagenes: list[str]) -> Dict[str, Any]:
    prompt = f"Fecha de situación: {fecha}\nTexto de la novedad: {texto}\n"
    if descripciones_imagenes:
        prompt += "Imágenes anexadas:\n" + "\n".join(f"- {d}" for d in descripciones_imagenes if d)

    async with _semaphore:
        return await asyncio.to_thread(_call, prompt)


def _call(prompt: str) -> Dict[str, Any]:
    try:
        response = groq_client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.groq_temperature,
            max_tokens=settings.groq_max_tokens,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("La IA no devolvió un JSON válido. Usando fallback.")
            return {"actores": [], "amenaza": "Desconocida", "analisis": content}
    except APITimeoutError:
        raise GroqAnalysisError("La IA Groq no respondió dentro del tiempo límite.")
    except APIError as e:
        raise GroqAnalysisError(f"Error en la API de Groq: {str(e)}")
