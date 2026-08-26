"""
AI ENGINE (Módulo Independiente Exportable)
===========================================
Gestor de inferencia multi-proveedor con balanceo de carga entre múltiples claves API,
rotación automática, circuit breaker y tolerancia a fallos para CometAPI, NVIDIA y Ollama.
"""

import asyncio
import hashlib
import itertools
import json
import logging
import os
import random
import threading
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv(override=True)
logger = logging.getLogger("AIEngine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ── Disyuntor (Circuit Breaker) ───────────────────────────────────
class CircuitBreaker:
    def __init__(self, name: str, threshold: int = 5, recovery: float = 60.0):
        self.name = name
        self.threshold = threshold
        self.recovery = recovery
        self._state = "CLOSED"
        self._failures = 0
        self._last_open = 0.0
        self._lock = threading.Lock()

    @property
    def is_available(self) -> bool:
        with self._lock:
            if self._state == "OPEN":
                if time.time() - self._last_open > self.recovery:
                    self._state = "HALF-OPEN"
                    return True
                return False
            return True

    def success(self):
        with self._lock:
            self._failures = 0
            self._state = "CLOSED"

    def failure(self):
        with self._lock:
            self._failures += 1
            if self._failures >= self.threshold:
                self._state = "OPEN"
                self._last_open = time.time()
                logger.warning(f"[CIRCUIT BREAKER] {self.name} ABIERTO por {self._failures} fallos.")


_global_cb = CircuitBreaker("AI_Pool", threshold=5, recovery=45.0)

# ── Pool de Clientes y Rotación de API Keys ───────────────────────
_ai_pool: List[AsyncOpenAI] = []
_ai_pool_iter = None
_ai_pool_lock = threading.Lock()
_key_failures: Dict[str, int] = {}


def get_ai_pool() -> List[AsyncOpenAI]:
    """Inicializa y retorna la lista de clientes AsyncOpenAI para rotación."""
    keys = [
        os.getenv("COMETAPI_KEY_1"),
        os.getenv("COMETAPI_KEY_2"),
        os.getenv("COMETAPI_KEY_3"),
        os.getenv("COMETAPI_KEY_4"),
        os.getenv("COMETAPI_KEY_5"),
        os.getenv("COMETAPI_KEY"),
        os.getenv("OPENAI_API_KEY"),
        os.getenv("GROQ_API_KEY"),
        os.getenv("GROQ_API_KEY_COORD"),
        os.getenv("GROQ_API_KEY_ARES"),
        os.getenv("GROQ_API_KEY_NEXUS"),
        os.getenv("GROQ_API_KEY_MINERVA"),
    ]
    unique_keys = list(set([k.strip() for k in keys if k and k.strip()]))
    # Colocar primero las claves sk- (CometAPI) para compatibilidad nativa con gpt-4o / gpt-4o-mini
    unique_keys.sort(key=lambda k: 0 if k.startswith("sk-") else 1)

    clients: List[AsyncOpenAI] = []
    comet_base = os.getenv("COMETAPI_BASE_URL", "https://api.cometapi.com/v1")

    for k in unique_keys:
        base_url = comet_base if k.startswith("sk-") else "https://integrate.api.nvidia.com/v1"
        clients.append(AsyncOpenAI(api_key=k, base_url=base_url))

    return clients


def _init_pool():
    global _ai_pool, _ai_pool_iter
    with _ai_pool_lock:
        if _ai_pool_iter is None:
            _ai_pool = get_ai_pool()
            if _ai_pool:
                _ai_pool_iter = itertools.cycle(range(len(_ai_pool)))
                logger.info(f"[AI POOL] Pool inicializado con {len(_ai_pool)} clientes API.")


def get_next_client(max_retries: int = 5, only_sk: bool = False) -> Optional[AsyncOpenAI]:
    """Retorna el siguiente cliente API disponible del pool en rotación."""
    if not _global_cb.is_available:
        logger.warning("[CIRCUIT BREAKER] Pool en pausa por fallos acumulados.")
        return None

    _init_pool()
    if not _ai_pool:
        logger.error("[AI POOL] No hay claves API configuradas en .env")
        return None

    sk_clients = [c for c in _ai_pool if (c.api_key or "").startswith("sk-")]
    active_pool = sk_clients if (only_sk and sk_clients) else _ai_pool

    for _ in range(max_retries):
        with _ai_pool_lock:
            idx = next(_ai_pool_iter) if _ai_pool_iter else 0
        client = active_pool[idx % len(active_pool)]
        key_hash = hashlib.md5((client.api_key or "anon").encode()).hexdigest()[:10]

        if _key_failures.get(key_hash, 0) > 3:
            continue

        return client

    # Reset en caso de agotamiento temporal
    with _ai_pool_lock:
        _key_failures.clear()
        return active_pool[0] if active_pool else None


def report_success(client: AsyncOpenAI):
    key_hash = hashlib.md5((client.api_key or "anon").encode()).hexdigest()[:10]
    with _ai_pool_lock:
        _key_failures.pop(key_hash, None)
    _global_cb.success()


def report_failure(client: AsyncOpenAI):
    key_hash = hashlib.md5((client.api_key or "anon").encode()).hexdigest()[:10]
    with _ai_pool_lock:
        _key_failures[key_hash] = _key_failures.get(key_hash, 0) + 1
    _global_cb.failure()


# ── Función Principal de Inferencia Adaptativa ────────────────────
async def ask_ai(
    prompt: str,
    system_prompt: str = "Eres un asistente de análisis de datos profesional.",
    model: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.3,
    max_tokens: int = 800,
    max_retries: int = 3,
) -> Optional[str]:
    """Ejecuta una consulta a la IA con reintentos automáticos, balanceo y fallback de modelo."""
    selected_model = model or os.getenv("AI_MODEL", "gpt-4o")
    is_gpt_model = any(m in selected_model.lower() for m in ["gpt-", "claude-", "o1-", "o3-"])

    for attempt in range(max_retries):
        client = get_next_client(only_sk=is_gpt_model)
        if not client:
            await asyncio.sleep(1)
            continue

        try:
            kwargs = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await client.chat.completions.create(**kwargs)
            report_success(client)
            return response.choices[0].message.content.strip()

        except Exception as e:
            report_failure(client)
            error_str = str(e).lower()
            logger.warning(f"[AI RETRY {attempt + 1}/{max_retries}] Error con {selected_model}: {e}")

            # Fallback automático a gpt-4o-mini si gpt-4o presenta límite o tarifa
            if ("price" in error_str or "rate limit" in error_str or "429" in error_str) and selected_model != "gpt-4o-mini":
                logger.info("[FALLBACK] Reintentando con modelo ligero gpt-4o-mini...")
                selected_model = "gpt-4o-mini"

            await asyncio.sleep(1 + random.uniform(0.1, 0.5))

    return None
