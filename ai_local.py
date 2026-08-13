"""
ai_local.py - Fallback de IA local para cuando los proveedores externos fallan.
Usa transformers (modelo pequeño) o llama.cpp para inferencia local.
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)


def _ollama_defaults() -> dict:
    try:
        import config

        return {
            "enabled": bool(getattr(config, "OLLAMA_ENABLED", False)),
            "endpoint": f"http://{getattr(config, 'OLLAMA_HOST', '127.0.0.1')}:{getattr(config, 'OLLAMA_PORT', 11434)}/v1",
            "model": getattr(config, "OLLAMA_MODEL", "local-model"),
        }
    except Exception:
        return {"enabled": False, "endpoint": "http://127.0.0.1:1234/v1", "model": "local-model"}


_ollama_cfg = _ollama_defaults()

LOCAL_AI_ENABLED = (
    os.getenv("LOCAL_AI_ENABLED", "true" if _ollama_cfg["enabled"] else "false").lower() == "true"
)
LOCAL_AI_ENDPOINT = os.getenv("LOCAL_AI_ENDPOINT", _ollama_cfg["endpoint"])  # LM Studio / llama.cpp / Ollama /v1
LOCAL_AI_MODEL = os.getenv("LOCAL_AI_MODEL", _ollama_cfg["model"])
LOCAL_AI_TOKEN = os.getenv("LOCAL_AI_TOKEN", "")

# Caché simple para respuestas del modelo local (evita regenerar)
_local_cache = {}
_LOCAL_CACHE_MAX = 200


def _cache_key(prompt_hash: str) -> str:
    return f"local:{prompt_hash}"


def _get_cached(key: str) -> Optional[str]:
    return _local_cache.get(key)


def _set_cache(key: str, value: str):
    if len(_local_cache) >= _LOCAL_CACHE_MAX:
        for k in list(_local_cache.keys())[:50]:
            del _local_cache[k]
    _local_cache[key] = value


async def query_local_llm(prompt: str, max_tokens: int = 500, temperature: float = 0.3) -> Optional[str]:
    """Llama a un endpoint LLM local (LM Studio, llama.cpp, vLLM) compatible con OpenAI API."""
    if not LOCAL_AI_ENABLED:
        return None

    import hashlib

    pkey = _cache_key(hashlib.md5(prompt.encode()).hexdigest())
    cached = _get_cached(pkey)
    if cached:
        return cached

    try:
        from openai import AsyncOpenAI
        from ollama_provider import ollama_settings
        ollama_cfg = ollama_settings()

        client = AsyncOpenAI(
            base_url=LOCAL_AI_ENDPOINT,
            api_key=LOCAL_AI_TOKEN or "not-needed",
        )
        # Usar el modelo local configurado para Ollama/LMStudio, no el modelo remoto de la nube
        local_model = ollama_cfg["model"] if ollama_cfg["enabled"] else LOCAL_AI_MODEL
        response = await client.chat.completions.create(
            model=local_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content.strip()
        _set_cache(pkey, text)
        logger.info("[LOCAL AI] Respuesta generada localmente")
        return text
    except ImportError:
        logger.warning("[LOCAL AI] openai no instalado. Local AI no disponible.")
        return None
    except Exception as e:
        logger.warning(f"[LOCAL AI] Error: {e}")
        return None


def generate_local_summary(text: str, max_len: int = 200) -> str:
    """Genera un resumen simple basado en reglas cuando no hay LLM disponible."""
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    summary = []
    char_count = 0
    for s in sentences:
        if char_count + len(s) > max_len:
            break
        summary.append(s)
        char_count += len(s)
    result = " ".join(summary)
    if len(result) < len(text):
        result += " [...]"
    return result if result else text[:max_len] + "..."


def extract_keywords_local(text: str, max_keywords: int = 5) -> list:
    """Extrae palabras clave simples basadas en frecuencia."""
    words = re.findall(r"\b[a-zA-Záéíóúñ]{4,}\b", text.lower())
    freq = {}
    stop_words = {
        "para",
        "como",
        "entre",
        "sobre",
        "este",
        "esta",
        "esto",
        "más",
        "menos",
        "tiene",
        "puede",
        "hace",
        "todo",
        "parte",
        "tras",
        "cada",
        "sino",
        "cual",
    }
    for w in words:
        if w not in stop_words:
            freq[w] = freq.get(w, 0) + 1
    sorted_kw = sorted(freq.items(), key=lambda x: -x[1])
    return [kw for kw, _ in sorted_kw[:max_keywords]]
