import asyncio
import hashlib
import itertools
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import List, Optional

import aiohttp
from dotenv import load_dotenv
from openai import AsyncOpenAI as AsyncGroq

from humanization import RATE_LIMITERS, STRESS_MONITOR, wait_for_rate_limit_async
from security_utils import sanitize_html

load_dotenv(override=True)
logger = logging.getLogger(__name__)


# ── Circuit Breaker ────────────────────────────────────────────────
class CircuitBreakerState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CircuitBreaker:
    """Disyuntor para APIs externas. Abre tras N fallos consecutivos,
    cierra tras timeout de recuperación, permitiendo tráfico de prueba."""

    def __init__(self, name: str, threshold: int = 5, recovery: float = 60.0):
        self.name = name
        self.threshold = threshold
        self.recovery = recovery
        self._state = CircuitBreakerState.CLOSED
        self._failures = 0
        self._last_open = 0.0
        self._lock = threading.Lock()

    @property
    def is_available(self) -> bool:
        with self._lock:
            if self._state == CircuitBreakerState.OPEN:
                if time.time() - self._last_open > self.recovery:
                    self._state = CircuitBreakerState.HALF_OPEN
                    return True
                return False
            return True

    def success(self):
        with self._lock:
            self._failures = 0
            self._state = CircuitBreakerState.CLOSED

    def failure(self):
        with self._lock:
            self._failures += 1
            if self._failures >= self.threshold:
                self._state = CircuitBreakerState.OPEN
                self._last_open = time.time()
                logger.warning(
                    f"[CIRCUIT BREAKER] {self.name} ABIERTO por {self._failures} fallos. "
                    f"Reintentando en {self.recovery}s."
                )

    def __repr__(self):
        return f"CircuitBreaker({self.name}, state={self._state}, failures={self._failures})"


# Disyuntor global para el pool genérico Groq
_groq_cb = CircuitBreaker("Groq", threshold=5, recovery=60.0)


def is_ai_available() -> bool:
    """Retorna True si el pool Groq está disponible (o si IA local está habilitada)."""
    try:
        from ollama_provider import ollama_settings

        if ollama_settings()["enabled"]:
            return True
    except Exception:
        pass
    return _groq_cb.is_available


# ── Locks para estado global ──────────────────────
_ai_cache_lock = threading.Lock()
_ai_session_lock = asyncio.Lock()
_groq_pool_lock = threading.Lock()

# ── Sesión Global para APIs Externas ─────────────────────────────
_ai_session: Optional[aiohttp.ClientSession] = None


async def get_ai_session() -> aiohttp.ClientSession:
    """Retorna una sesión aiohttp compartida para evitar overhead de TLS."""
    global _ai_session
    async with _ai_session_lock:
        if _ai_session is None or _ai_session.closed:
            _ai_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30), headers={"User-Agent": "CobaltoHub-AI/9.0"}
            )
    return _ai_session


async def close_ai_session():
    """Cierra la sesión global de aiohttp de manera segura para evitar fugas de sockets."""
    global _ai_session
    async with _ai_session_lock:
        if _ai_session and not _ai_session.closed:
            try:
                await _ai_session.close()
                logger.info("[AI SESSION] Sesión global de aiohttp cerrada de manera segura.")
            except Exception as e:
                logger.error(f"[AI SESSION] Error al cerrar sesión global: {e}")


# ── Caché simple de resultados de IA ─────────────────────────────
_ai_cache = {}
_AI_CACHE_MAX = 5000


def _cache_key(text: str, prefix: str = "") -> str:
    return f"{prefix}:{hashlib.md5(text.encode('utf-8')).hexdigest()}"


def _cache_get(key: str):
    with _ai_cache_lock:
        return _ai_cache.get(key)


def _cache_set(key: str, value):
    with _ai_cache_lock:
        if len(_ai_cache) >= _AI_CACHE_MAX:
            try:
                # Eliminar el 20% más antiguo usando FIFO
                for _ in range(_AI_CACHE_MAX // 5):
                    _ai_cache.pop(next(iter(_ai_cache)), None)
            except StopIteration:
                _ai_cache.clear()
        _ai_cache[key] = value


def ai_adaptive_call(func):
    """Decorador que aplica rate limiting adaptativo a las llamadas de IA."""

    async def wrapper(*args, **kwargs):
        limiter = RATE_LIMITERS.get("ai_groq")
        retry_count = 0
        max_retries = 3
        import random as _random

        while retry_count < max_retries:
            await wait_for_rate_limit_async("ai_groq")
            try:
                result = await func(*args, **kwargs)
                if limiter:
                    limiter.report_status(200 if result is not None else 429)
                return result
            except Exception as e:
                error_str = str(e).lower()
                if "rate limit" in error_str or "429" in error_str:
                    logger.warning(f"[AI LIMIT] Rate limit detectado. Aplicando backoff... ({retry_count + 1})")
                    if limiter:
                        limiter.report_status(429)
                    retry_count += 1
                    await asyncio.sleep((2**retry_count) + _random.uniform(0, 1))
                else:
                    logger.error(f"[AI ERROR] Error no recuperable: {e}")
                    if limiter:
                        limiter.report_status(500)
                    raise e
        return None

    return wrapper


# ── Gestión de Claves y Clientes (Pool de Balanceo) ────────────────

_groq_pool: List[AsyncGroq] = []
_groq_pool_iter = None
_groq_key_errors: dict = {}  # api_key -> consecutive_failures


def get_groq_pool() -> List[AsyncGroq]:
    """Obtiene los clientes Groq del pool genérico.
    Incluye claves genéricas y de agente como respaldo para maximizar throughput.
    Si la IA local (Ollama) está habilitada, se inserta como primer cliente del pool."""
    keys = [
        os.getenv("GROQ_API_KEY"),
        os.getenv("GROQ_API_KEY_2"),
        os.getenv("GROQ_API_KEY_3"),
        os.getenv("GROQ_API_KEY_COORD"),
        os.getenv("GROQ_API_KEY_ARES"),
        os.getenv("GROQ_API_KEY_NEXUS"),
        os.getenv("GROQ_API_KEY_MINERVA"),
    ]
    unique_keys = list(set([k for k in keys if k]))
    clients: List[AsyncGroq] = [
        AsyncGroq(api_key=k, base_url="https://integrate.api.nvidia.com/v1") for k in unique_keys
    ]
    try:
        from ollama_provider import OllamaCompatClient, ollama_settings

        if ollama_settings()["enabled"]:
            clients.insert(0, OllamaCompatClient())
    except Exception as e:
        logger.warning(f"[OLLAMA] No se pudo añadir Ollama al pool: {e}")
    return clients


def _init_groq_pool():
    """Inicializa el pool si es necesario."""
    global _groq_pool, _groq_pool_iter, _groq_key_errors
    with _groq_pool_lock:
        if _groq_pool_iter is None:
            _groq_pool = get_groq_pool()
            _groq_key_errors = {}
            if _groq_pool:
                _groq_pool_iter = itertools.cycle(range(len(_groq_pool)))
                logger.info(f"[GROQ POOL] {len(_groq_pool)} clientes disponibles")


def get_next_groq_client(max_retries=5) -> Optional[AsyncGroq]:
    """Retorna el siguiente cliente Groq saludable (salta keys con fallos consecutivos)."""
    if not _groq_cb.is_available:
        logger.warning("[CIRCUIT BREAKER] Groq abierto. Saltando pool.")
        return None

    _init_groq_pool()
    if not _groq_pool:
        return None

    for _ in range(max_retries):
        with _groq_pool_lock:
            idx = next(_groq_pool_iter) if _groq_pool_iter else 0
        if idx >= len(_groq_pool):
            break

        client = _groq_pool[idx]
        api_key = client.api_key if client.api_key else "unknown"
        api_key_hash = hashlib.md5(api_key.encode()).hexdigest()[:16]

        # Saltar si esta key ha fallado >3 veces consecutivas
        if _groq_key_errors.get(api_key_hash, 0) > 3:
            continue

        return client

    # Reset temporal: todas las keys han fallado, reintentar desde principio
    logger.warning("[GROQ POOL] Todas las keys penalizadas. Reiniciando contadores.")
    with _groq_pool_lock:
        _groq_key_errors.clear()
        if _groq_pool:
            return _groq_pool[0]
    return None


# ── Clientes dedicados por agente ──────────────────────────────────
_agent_clients: dict = {}


def _get_agent_client(env_var: str) -> Optional[AsyncGroq]:
    """Crea/cachea un cliente Groq dedicado para una env var específica."""
    key = os.getenv(env_var)
    if not key:
        return None
    if env_var not in _agent_clients or _agent_clients[env_var] is None:
        _agent_clients[env_var] = AsyncGroq(api_key=key, base_url="https://integrate.api.nvidia.com/v1")
    return _agent_clients[env_var]


def _api_key_hash(client: AsyncGroq) -> str:
    api_key = client.api_key if client.api_key else "unknown"
    return hashlib.md5(api_key.encode()).hexdigest()[:16]


def report_groq_success(client: AsyncGroq):
    """Reporta éxito y resetea contador de errores para esta key."""
    api_key_hash = _api_key_hash(client)
    with _groq_pool_lock:
        _groq_key_errors.pop(api_key_hash, None)
    _groq_cb.success()
    STRESS_MONITOR.record_ai_success()


def report_groq_failure(client: AsyncGroq):
    """Incrementa contador de fallos para esta key."""
    api_key_hash = _api_key_hash(client)
    with _groq_pool_lock:
        _groq_key_errors[api_key_hash] = _groq_key_errors.get(api_key_hash, 0) + 1
    _groq_cb.failure()
    STRESS_MONITOR.record_ai_failure()


async def geolocate_text(text: str) -> dict:
    """Extrae la Latitud y Longitud exacta de un texto usando heurística rápida con fallback a LLM."""

    # 1. Capa Heurística Ultrarrápida (RAM)
    try:
        from dashboard_geocontext import fast_geolocate_venezuela
        fast_results = fast_geolocate_venezuela(text)
        if fast_results:
            return {"lat": fast_results[0]["lat"], "lon": fast_results[0]["lon"]}
    except ImportError:
        pass

    # 2. Capa LLM (Fallback)
    ck = _cache_key(text[:500], "geo")
    cached = _cache_get(ck)
    if cached:
        return cached

    client = get_next_groq_client()
    if not client:
        return {"lat": None, "lon": None}

    prompt = f"""Localiza geográficamente la siguiente noticia sobre Venezuela.
    Responde ÚNICAMENTE con un JSON con 'lat' y 'lon'. Si no hay lugar específico, usa null.
    Noticia: {text[:500]}"""

    @ai_adaptive_call
    async def _call():
        import config
        return await client.chat.completions.create(
            model=config.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100,
            response_format={"type": "json_object"},
        )

    try:
        response = await _call()
        if not response:
            return {"lat": None, "lon": None}
        report_groq_success(client)
        content = response.choices[0].message.content.strip()
        result = json.loads(content)
        _cache_set(ck, result)
        return result
    except Exception as e:
        report_groq_failure(client)
        logger.warning(f"Error Geolocalizando: {e}")
        try:
            from ai_local import LOCAL_AI_ENABLED, query_local_llm
            if LOCAL_AI_ENABLED:
                logger.info("[GEO FALLBACK] Groq falló. Intentando LLM local...")
                local_res = await query_local_llm(prompt, max_tokens=100, temperature=0.1)
                if local_res:
                    result = json.loads(local_res)
                    _cache_set(ck, result)
                    return result
        except Exception as local_ex:
            logger.warning(f"[GEO FALLBACK] Error al intentar LLM local: {local_ex}")

    return {"lat": None, "lon": None}


_briefing_in_progress = None
_briefing_in_progress_lock = threading.Lock()
_briefing_step = {}
_briefing_step_lock = threading.Lock()
_BRIEFING_CACHE_MAX = 10
_briefing_cache = {}


def set_briefing_step(step: str, status: str):
    with _briefing_step_lock:
        _briefing_step["step"] = step
        _briefing_step["status"] = status
        _briefing_step["timestamp"] = datetime.now().strftime("%H:%M:%S")


def get_briefing_step() -> dict:
    with _briefing_step_lock:
        return dict(_briefing_step)


def clear_briefing_step():
    with _briefing_step_lock:
        _briefing_step.clear()


def _briefing_context_hash(news_entries, alerts, fakenews) -> str:
    """Hash del contexto para evitar re-debates cuando los datos no cambiaron."""
    raw = json.dumps([n.get("title") for n in news_entries[:40]], sort_keys=True)
    raw += str(len(alerts or [])) + str(len(fakenews or []))
    return hashlib.md5(raw.encode()).hexdigest()[:16]


TIME_AGENT_PROMPTS = {
    "IA-ARES": {
        "keywords": [
            "militar",
            "ejército",
            "fanb",
            "armas",
            "conflicto",
            "guerra",
            "tropas",
            "general",
            "coronel",
            "comandante",
            "patrulla",
            "vehículo blindado",
            "tanque",
            "helicóptero",
            "avión militar",
            "base militar",
            "cuartel",
            "operación militar",
            "movilización",
            "seguridad",
            "defensa",
            "combate",
            "choque",
            "enfrentamiento",
            "insurgencia",
            "guerrilla",
            "paramilitar",
            "mercenario",
        ]
    },
    "IA-MINERVA": {
        "keywords": [
            "gobierno",
            "presidente",
            "ministerio",
            "embajada",
            "diplomático",
            "sanción",
            "economía",
            "dólar",
            "bcv",
            "inflación",
            "pib",
            "petróleo",
            "pdvsa",
            "opep",
            "deuda",
            "fmi",
            "comercio",
            "exportación",
            "importación",
            "arancel",
            "política",
            "elección",
            "asamblea",
            "constitución",
            "ley",
            "social",
            "protesta",
            "huelga",
            "manifestación",
            "derechos humanos",
            "amnistía",
        ]
    },
    "IA-NEXUS": {
        "keywords": [
            "ciber",
            "hacker",
            "ataque",
            "malware",
            "ransomware",
            "phishing",
            "filtración",
            "data breach",
            "ddos",
            "vulnerabilidad",
            "0day",
            "osint",
            "inteligencia",
            "señal",
            "interceptación",
            "vigilancia",
            "red",
            "internet",
            "telecomunicación",
            "satélite",
            "starlink",
            "defacement",
            "anonimato",
            "encriptación",
            "deep web",
            "onion",
            "telegram",
            "whatsapp",
            "signal",
            "desinformación",
            "fakenews",
        ]
    },
}


def _filter_news_for_agent(news_entries: list, agent_name: str, max_count: int = 15) -> str:
    """Filtra noticias por keywords relevantes al agente."""
    agent_config = TIME_AGENT_PROMPTS.get(agent_name)
    if not agent_config:
        return "\n".join(
            [
                f"- {n.get('title')} ({n.get('source')}): {n.get('summary', '')[:150]}..."
                for n in news_entries[:max_count]
            ]
        )

    keywords = agent_config["keywords"]
    matched = []
    remaining = []

    for n in news_entries:
        text = f"{n.get('title', '')} {n.get('summary', '')}".lower()
        if any(kw in text for kw in keywords):
            matched.append(n)
        else:
            remaining.append(n)
        if len(matched) >= max_count:
            break

    selected = matched[:max_count]
    if len(selected) < max_count:
        selected += remaining[: max_count - len(selected)]

    lines = [f"- {n.get('title')} ({n.get('source')}): {n.get('summary', '')[:150]}..." for n in selected]
    return "\n".join(lines)


_AGENT_ERROR = "Fallo de comunicación."


def _is_agent_error(text: str) -> bool:
    return not text or text in (_AGENT_ERROR, "Sin conexión con LLM disponible.")


async def generate_global_briefing(news_entries, alerts=None, fakenews=None, mode="full"):
    ctx_hash = _briefing_context_hash(news_entries, alerts, fakenews)

    if mode == "full":
        cached = _briefing_cache.get(ctx_hash)
        if cached:
            return cached

    if not news_entries:
        return {
            "agents": [],
            "debate": [],
            "consensus": "No hay noticias relevantes en las últimas 24h para analizar.",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }

    memoria_tactica = ""
    if alerts:
        criticas = [a["title"] for a in alerts if "CRÍTICO" in a.get("level", "")]
        if criticas:
            memoria_tactica += f"\n[SISTEMA - ALERTA CRÍTICA ACTIVA]: {', '.join(criticas[:3])}"
    if fakenews:
        falsas = [f["title"] for f in fakenews if f.get("reliability_level") in ["BAJA", "MUY BAJA"]]
        if falsas:
            memoria_tactica += f"\n[SISTEMA - FAKE NEWS DETECTADA]: Las siguientes noticias son probable desinformación: {', '.join(falsas[:3])}"

    def _build_context(agent_name: str, max_count: int = 15) -> str:
        ctx = _filter_news_for_agent(news_entries, agent_name, max_count)
        if memoria_tactica:
            ctx = f"{memoria_tactica}\n\nNOTICIAS:\n{ctx}"
        # Truncar para evitar 413 Payload Too Large (TPM limit ~12000 tokens ≈ 48000 chars)
        if len(ctx) > 40000:
            ctx = ctx[:40000] + "\n[TRUNCATED: contexto excede límite de tokens]"
        return ctx

    @ai_adaptive_call
    async def _call_agent_groq(client, agent_name, agent_role, color, context):
        import config
        # Asignación de lineamiento político según el agente
        if "Neutral" in agent_name or "ARES" in agent_name:
            partisan_instruction = config.AI_SYSTEM_PROMPT_ARES
        elif "Oposición" in agent_name or "MINERVA" in agent_name:
            partisan_instruction = config.AI_SYSTEM_PROMPT_MINERVA
        elif "Oficialismo" in agent_name or "NEXUS" in agent_name:
            partisan_instruction = config.AI_SYSTEM_PROMPT_NEXUS
        else:
            partisan_instruction = "Mantén un análisis táctico profesional, equilibrado y objetivo de la situación."

        # Dar más oportunidad de expresión a Minerva (Oposición) y Nexus (Oficialismo) para enriquecer el debate.
        is_debate_agent = "MINERVA" in agent_name or "NEXUS" in agent_name
        word_limit = 300 if is_debate_agent else 150
        max_tokens_val = config.AI_MAX_TOKENS if is_debate_agent else min(500, config.AI_MAX_TOKENS)
        debate_emphasis = (
            " Dado tu rol clave en el debate geopolítico, expande tus argumentos, profundiza en el análisis crítico, y expón con detalle tus puntos y contraargumentos de manera elocuente."
            if is_debate_agent
            else ""
        )

        prompt = f"""Actúa como {agent_name}, {agent_role} de 'COBALTO HUB'.
{partisan_instruction}

Analiza las noticias proporcionadas de las últimas 24h desde tu enfoque analítico:

{context}

Responde de forma concisa, directa, fría y profesional en un máximo de {word_limit} palabras.{debate_emphasis}
CITA las fuentes específicas que sustentan tu análisis (medios de comunicación o cuentas).
No uses introducciones genéricas ni markdown, responde directamente tu análisis en texto plano."""

        try:
            response = await client.chat.completions.create(
                model=config.AI_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=config.AI_TEMPERATURE,
                max_tokens=max_tokens_val,
            )
            report_groq_success(client)
            text = response.choices[0].message.content.strip()
            text = text.replace("**", "").replace("*", "").replace("#", "")
            return {"agent": agent_name, "role": agent_role, "color": color, "text": sanitize_html(text)}
        except Exception as e:
            error_str = str(e).lower()
            # Fallback a modelo ligero cuando hay Rate Limit en el modelo grande
            if "rate limit" in error_str or "429" in error_str or "413" in error_str or "payload too large" in error_str:
                logger.warning(f"[RATE LIMIT / PAYLOAD] {agent_name}: {config.AI_MODEL} agotado. Reintentando con meta/llama-3.1-8b-instruct...")
                try:
                    response = await client.chat.completions.create(
                        model="meta/llama-3.1-8b-instruct",
                        messages=[{"role": "system", "content": prompt}],
                        temperature=config.AI_TEMPERATURE,
                        max_tokens=min(max_tokens_val, 600),
                    )
                    report_groq_success(client)
                    text = response.choices[0].message.content.strip()
                    text = text.replace("**", "").replace("*", "").replace("#", "")
                    logger.info(f"[RATE LIMIT FALLBACK] {agent_name}: llama-3.1-8b respondió OK")
                    return {"agent": agent_name, "role": agent_role, "color": color, "text": sanitize_html(text)}
                except Exception as e2:
                    report_groq_failure(client)
                    logger.error(f"Error {agent_name} (fallback 8b): {type(e2).__name__}: {e2}")
            else:
                report_groq_failure(client)
                logger.error(f"Error {agent_name}: {type(e).__name__}: {e}")
            return {"agent": agent_name, "text": _AGENT_ERROR, "color": color}

    async def _call_agent(client, agent_name, agent_role, color, fallback_client, context):
        import config
        from ai_local import LOCAL_AI_ENABLED, query_local_llm

        prefer_local = getattr(config, "PREFER_LOCAL_AI", True) or getattr(config, "OLLAMA_ENABLED", True)

        # Primer intento: Inferencia Local (Ollama) si está activa la preferencia o la IA local
        if prefer_local and LOCAL_AI_ENABLED:
            try:
                logger.info(f"[AI LOCAL PRIMARY] Ejecutando {agent_name} con LLM local...")
                if "Neutral" in agent_name or "ARES" in agent_name:
                    partisan_instruction = config.AI_SYSTEM_PROMPT_ARES
                elif "Oposición" in agent_name or "MINERVA" in agent_name:
                    partisan_instruction = config.AI_SYSTEM_PROMPT_MINERVA
                elif "Oficialismo" in agent_name or "NEXUS" in agent_name:
                    partisan_instruction = config.AI_SYSTEM_PROMPT_NEXUS
                else:
                    partisan_instruction = "Mantén un análisis táctico profesional, equilibrado y objetivo de la situación."

                is_debate_agent = "MINERVA" in agent_name or "NEXUS" in agent_name
                word_limit = 300 if is_debate_agent else 150
                max_tokens_val = config.AI_MAX_TOKENS if is_debate_agent else min(500, config.AI_MAX_TOKENS)
                debate_emphasis = (
                    " Dado tu rol clave en el debate geopolítico, expande tus argumentos, profundiza en el análisis crítico, y expón con detalle tus puntos y contraargumentos de manera elocuente."
                    if is_debate_agent
                    else ""
                )

                prompt = f"""Actúa como {agent_name}, {agent_role} de 'COBALTO HUB'.
{partisan_instruction}

Analiza las noticias proporcionadas de las últimas 24h desde tu enfoque analítico:

{context}

Responde de forma concisa, directa, fría y profesional en un máximo de {word_limit} palabras.{debate_emphasis}
CITA las fuentes específicas que sustentan tu análisis (medios de comunicación o cuentas).
No uses introducciones genéricas ni markdown, responde directamente tu análisis en texto plano."""

                local_text = await query_local_llm(prompt, max_tokens=max_tokens_val, temperature=config.AI_TEMPERATURE)
                if local_text:
                    local_text = local_text.replace("**", "").replace("*", "").replace("#", "")
                    return {"agent": agent_name, "role": agent_role, "color": color, "text": sanitize_html(local_text)}
            except Exception as ex:
                logger.warning(f"[AI LOCAL] Intento local falló para {agent_name}: {ex}")

        # Segundo intento: APIs externas si están presentes y configuradas
        if client:
            result = await _call_agent_groq(client, agent_name, agent_role, color, context)
            if result and not _is_agent_error(result.get("text", "")):
                return result
        if fallback_client:
            result = await _call_agent_groq(fallback_client, agent_name, agent_role, color, context)
            if result and not _is_agent_error(result.get("text", "")):
                return result

        return {"agent": agent_name, "text": "Sin conexión con LLM disponible.", "color": color}

    ares_client = _get_agent_client("GROQ_API_KEY_ARES")
    minerva_client = _get_agent_client("GROQ_API_KEY_MINERVA")
    nexus_client = _get_agent_client("GROQ_API_KEY_NEXUS")
    coord_client = _get_agent_client("GROQ_API_KEY_COORD")

    pool_client = get_next_groq_client()

    # --- MODO EXPRESS: solo COORD con pocas noticias ---
    if mode == "express":
        express_ctx = "\n".join(
            [f"- {n.get('title')} ({n.get('source')}): {n.get('summary', '')[:200]}..." for n in news_entries[:8]]
        )
        if memoria_tactica:
            express_ctx = f"{memoria_tactica}\n\nNOTICIAS:\n{express_ctx}"

        express_prompt = f"""Actúa como SISTEMA AGREGADOR DE INTELIGENCIA neutral.
Resume en 3 líneas la situación actual de Venezuela basado en estas noticias:

{express_ctx}

Responde directo, sin introducciones. Máximo 100 palabras."""

        async def _express_call():
            import config
            if coord_client:
                try:
                    response = await coord_client.chat.completions.create(
                        model=config.AI_MODEL,
                        messages=[{"role": "system", "content": express_prompt}],
                        temperature=config.AI_TEMPERATURE,
                        max_tokens=300,
                    )
                    report_groq_success(coord_client)
                    return response.choices[0].message.content.strip().replace("**", "")
                except Exception:
                    pass
            client = get_next_groq_client()
            if not client:
                return "Sin conexión."
            try:
                response = await client.chat.completions.create(
                    model=config.AI_MODEL,
                    messages=[{"role": "system", "content": express_prompt}],
                    temperature=config.AI_TEMPERATURE,
                    max_tokens=300,
                )
                report_groq_success(client)
                return response.choices[0].message.content.strip().replace("**", "")
            except Exception:
                return "Sin conexión."

        consensus_text = sanitize_html(await _express_call())
        return {
            "agents": [],
            "debate": [],
            "consensus": consensus_text,
            "mode": "express",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }

    # --- MODO FULL: debate entre agentes ---

    set_briefing_step("ARES", "procesando")

    # 1. ARES (Neutral) realiza la verificación fáctica inicial (OSINT) de las noticias
    ares_context = _build_context("IA-ARES", 15)
    ares_res = await _call_agent(
        ares_client,
        "IA-ARES (Neutral)",
        "Analista Neutral y de Verificación Fáctica (OSINT)",
        "#00ffaa",
        pool_client,
        ares_context,
    )
    ares_txt = ares_res.get("text", "") if isinstance(ares_res, dict) else str(ares_res)
    ares_ok = not _is_agent_error(ares_txt)
    set_briefing_step("MINERVA", "procesando")

    # 2. MINERVA (Oposición): interpreta los hechos neutrales establecidos por ARES bajo el prisma opositor
    if ares_ok:
        minerva_context = f"[IA-ARES (Neutral)] reporta los siguientes hechos objetivos confirmados:\n{ares_txt}\n\nAnaliza e interpreta estos hechos desde la perspectiva crítica y de la Oposición Venezolana. Identifica la crisis de servicios públicos, fallas estatales o descontento social en torno a esta información. CITA fuentes."
    else:
        minerva_context = _build_context("IA-MINERVA", 10)
        minerva_context = f"[IA-ARES (Neutral)] no disponible en este ciclo.\n\nContexto:\n{minerva_context}\n\nPresenta tu análisis crítico de oposición sobre el panorama actual. CITA fuentes."

    debate_minerva_res = await _call_agent(
        minerva_client,
        "IA-MINERVA (Oposición)",
        "Analista de Perspectiva Crítica y Oposición",
        "#44aaee",
        pool_client,
        minerva_context,
    )
    debate_minerva_txt = (
        debate_minerva_res.get("text", "") if isinstance(debate_minerva_res, dict) else str(debate_minerva_res)
    )
    minerva_ok = not _is_agent_error(debate_minerva_txt)
    set_briefing_step("NEXUS", "procesando")

    # 3. NEXUS (Oficialismo): toma el debate y responde directamente a la interpretación de la Oposición (MINERVA)
    nexus_debate = f"[IA-ARES (Neutral)] reportó los hechos objetivos:\n{ares_txt}\n\n[IA-MINERVA (Oposición)] los interpreta críticamente:\n{debate_minerva_txt}\n\n"
    nexus_own_ctx = _build_context("IA-NEXUS", 10)
    nexus_context = f"{nexus_debate}Responde directamente a la narrativa crítica de la Oposición. Presenta la postura del oficialismo y defensa soberana sobre estos mismos hechos, destacando el impacto de sanciones y la respuesta estatal.\n\nContexto complementario:\n{nexus_own_ctx}"

    debate_nexus_res = await _call_agent(
        nexus_client,
        "IA-NEXUS (Oficialismo)",
        "Analista de Perspectiva Oficialista y Defensa Soberana",
        "#ff4444",
        pool_client,
        nexus_context,
    )
    debate_nexus_txt = debate_nexus_res.get("text", "") if isinstance(debate_nexus_res, dict) else str(debate_nexus_res)
    nexus_ok = not _is_agent_error(debate_nexus_txt)
    set_briefing_step("AGREGADOR", "procesando")

    set_briefing_step("NEXUS", "completado")

    # El Consenso Estratégico (antiguo Agente Cobalto) fue movido
    # a la pestaña dedicada de Sentimiento/PsyOps (analyze_psyops_sentiment_async).
    # Ya no se genera en este pipeline principal para ahorrar tokens y tiempo.
    consensus_text = ""

    # Construir agent y debate lists limpias
    agents_out = []
    if ares_ok:
        agents_out.append(ares_res)
    debate_out = []
    if minerva_ok:
        debate_out.append(
            {
                "agent": "IA-MINERVA (Oposición)",
                "role": "Analista de Perspectiva Crítica y Oposición",
                "color": "#44aaee",
                "text": sanitize_html(debate_minerva_txt),
            }
        )
    if nexus_ok:
        debate_out.append(
            {
                "agent": "IA-NEXUS (Oficialismo)",
                "role": "Analista de Perspectiva Oficialista y Defensa Soberana",
                "color": "#ff4444",
                "text": sanitize_html(debate_nexus_txt),
            }
        )

    result = {
        "agents": agents_out,
        "debate": debate_out,
        "consensus": consensus_text,
        "mode": "full",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }

    if mode == "full":
        if len(_briefing_cache) >= _BRIEFING_CACHE_MAX:
            _briefing_cache.clear()
        _briefing_cache[ctx_hash] = result

    return result


async def analyze_sentiment(text: str) -> dict:
    """Analiza el sentimiento de un texto sobre Venezuela."""
    ck = _cache_key(text[:500], "sent")
    cached = _cache_get(ck)
    if cached:
        return cached

    client = get_next_groq_client()
    if not client:
        return {"sentiment": "unknown", "score": 0, "confidence": 0}
    prompt = f"""Analiza el sentimiento de esta noticia sobre Venezuela.
Devuelve ÚNICAMENTE un JSON con formato:
{{"sentiment": "positivo|negativo|neutral", "score": -1 a 1, "confidence": 0 a 100}}
Texto: {text[:500]}"""

    @ai_adaptive_call
    async def _call():
        import config
        return await client.chat.completions.create(
            model=config.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=80,
            response_format={"type": "json_object"},
        )

    try:
        response = await _call()
        if not response:
            return {"sentiment": "neutral", "score": 0, "confidence": 0}
        report_groq_success(client)
        content = response.choices[0].message.content.strip()
        result = json.loads(content)
        _cache_set(ck, result)
        return result
    except Exception as e:
        report_groq_failure(client)
        logger.warning(f"Error en análisis de sentimiento: {e}")
        try:
            from ai_local import LOCAL_AI_ENABLED, query_local_llm
            if LOCAL_AI_ENABLED:
                logger.info("[SENTIMENT FALLBACK] Groq falló. Intentando LLM local...")
                local_res = await query_local_llm(prompt, max_tokens=80, temperature=0.1)
                if local_res:
                    result = json.loads(local_res)
                    _cache_set(ck, result)
                    return result
        except Exception as local_ex:
            logger.warning(f"[SENTIMENT FALLBACK] Error al intentar LLM local: {local_ex}")

    return {"sentiment": "neutral", "score": 0, "confidence": 0}


async def extract_entities(text: str) -> dict:
    """Extrae entidades nombradas (NER) de un texto sobre Venezuela."""
    ck = _cache_key(text[:800], "ner")
    cached = _cache_get(ck)
    if cached:
        return cached

    client = get_next_groq_client()
    if not client:
        return {"persons": [], "organizations": [], "locations": [], "events": []}
    prompt = f"""Extrae las entidades nombradas de este texto sobre Venezuela.
Devuelve ÚNICAMENTE un JSON con formato:
{{"persons": [], "organizations": [], "locations": [], "events": []}}
Texto: {text[:800]}"""

    @ai_adaptive_call
    async def _call():
        import config
        return await client.chat.completions.create(
            model=config.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=150,
            response_format={"type": "json_object"},
        )

    try:
        response = await _call()
        if not response:
            return {"persons": [], "organizations": [], "locations": [], "events": []}
        report_groq_success(client)
        content = response.choices[0].message.content.strip()
        result = json.loads(content)
        _cache_set(ck, result)
        return result
    except Exception as e:
        report_groq_failure(client)
        logger.warning(f"Error en extracción de entidades: {e}")
        try:
            from ai_local import LOCAL_AI_ENABLED, query_local_llm
            if LOCAL_AI_ENABLED:
                logger.info("[NER FALLBACK] Groq falló. Intentando LLM local...")
                local_res = await query_local_llm(prompt, max_tokens=150, temperature=0.1)
                if local_res:
                    result = json.loads(local_res)
                    _cache_set(ck, result)
                    return result
        except Exception as local_ex:
            logger.warning(f"[NER FALLBACK] Error al intentar LLM local: {local_ex}")

    return {"persons": [], "organizations": [], "locations": [], "events": []}


async def analyze_psyops_sentiment_async(sentiment_data: dict) -> str:
    """
    Genera un informe de Operaciones Psicológicas (PsyOps) basado en los datos
    del análisis de sentimiento del corpus actual.
    Importado y llamado por osint_sentiment.get_sentiment_data().
    """
    # Cache: evitar re-generar si los datos no cambiaron significativamente
    cache_key_data = (
        f"psyops:{sentiment_data.get('score_global', 0):.2f}:"
        f"{sentiment_data.get('nivel_alerta', '')}:"
        f"{sentiment_data.get('bot_rate', 0)}:"
        f"{sentiment_data.get('total_analizadas', 0)}"
    )
    ck = _cache_key(cache_key_data, "psyops")
    cached = _cache_get(ck)
    if cached:
        return cached

    client = get_next_groq_client()
    if not client:
        return "Mando Central Cobalto: LLM no disponible en este ciclo."

    # Construir contexto táctico compacto
    score = sentiment_data.get("score_global", 0.0)
    nivel = sentiment_data.get("nivel_alerta", "DESCONOCIDO")
    bot_rate = sentiment_data.get("bot_rate", 0.0)
    bots_n = sentiment_data.get("bots_detectados", 0)
    total = sentiment_data.get("total_analizadas", 0)
    alertas_criticas = sentiment_data.get("alertas_criticas", 0)
    alertas_atencion = sentiment_data.get("alertas_atencion", 0)

    dist = sentiment_data.get("distribucion", {})
    pct_pos = round(dist.get("positivo", 0) / max(1, total) * 100, 1)
    pct_neg = round(dist.get("negativo", 0) / max(1, total) * 100, 1)

    # Narrativas más relevantes
    narrativas = sentiment_data.get("narrativas_geo", [])[:4]
    narrativa_txt = "; ".join(
        [f"{n['nombre']} (score {n['score_promedio']:+.2f}, {n['menciones']} menciones)" for n in narrativas]
    ) if narrativas else "Sin narrativas detectadas"

    # CIB
    cib = sentiment_data.get("cib", {})
    cib_alerta = cib.get("alerta_cib", False)
    cib_clusters = len(cib.get("clusters", []))
    cib_msg = f"ALERTA CIB: {cib.get('nivel', 'N/A')} — {cib_clusters} cluster(s) coordinados" if cib_alerta else "Sin evidencia de coordinación inauténtica"

    # Palabras top negativas
    top_neg = sentiment_data.get("top_palabras_neg", [])[:5]
    palabras_neg_txt = ", ".join([f"'{w['word']}' ({w['count']})" for w in top_neg]) if top_neg else "ninguna"

    # Overton
    overton = sentiment_data.get("overton_emergentes", [])[:3]
    overton_txt = ", ".join([f"'{e['termino']}' (+{e['ratio_cambio']}x)" for e in overton]) if overton else "sin términos emergentes"

    prompt = f"""Eres COBALTO, el Analista Jefe de Operaciones Psicológicas (PsyOps) e Inteligencia Informacional de la red COBALTO HUB.

DATOS DE TELEMETRÍA EMOCIONAL — CICLO ACTUAL:
• Corpus analizado: {total} entradas
• Score global de sentimiento: {score:+.3f} | Nivel: {nivel}
• Distribución: {pct_pos}% positivo / {pct_neg}% negativo
• Tasa de bots/influencia: {bot_rate}% ({bots_n} detectados)
• Alertas de crisis activas: {alertas_criticas} críticas + {alertas_atencion} de atención
• {cib_msg}
• Narrativas geopolíticas dominantes: {narrativa_txt}
• Señales léxicas de mayor carga negativa: {palabras_neg_txt}
• Términos emergentes (Overton): {overton_txt}

Con base en estos datos, emite un informe PsyOps táctico ESTRUCTURADO en formato JSON ESTRICTO.
El JSON debe contener exactamente estas claves:
{{
  "operacion_influencia": "Breve diagnóstico (máx 20 palabras) sobre si existe coordinación o astroturfing activo.",
  "vector_manipulacion": "Táctica cognitiva detectada (ej. 'Apelación al miedo', 'Efecto Bandwagon', etc.) y justificación breve.",
  "contramedida": "Recomendación táctica para mitigar la narrativa.",
  "nivel_amenaza": "VERDE, AMARILLO, NARANJA o ROJO"
}}

SOLO devuelve el JSON, sin backticks ni texto adicional."""

    import config

    try:
        response = await client.chat.completions.create(
            model=config.AI_MODEL,
            messages=[{"role": "system", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        report_groq_success(client)
        text = response.choices[0].message.content.strip()
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            result = {"operacion_influencia": "Error procesando JSON", "vector_manipulacion": "-", "contramedida": "-", "nivel_amenaza": "DESCONOCIDO"}

        _cache_set(ck, result)
        return result
    except Exception as e:
        error_str = str(e).lower()
        report_groq_failure(client)
        logger.warning(f"[PSYOPS] Error generando informe: {e}")

        # Fallback a modelo diferente si hay rate limit
        if "rate limit" in error_str or "429" in error_str:
            fallback_client = get_next_groq_client()
            if fallback_client:
                try:
                    response = await fallback_client.chat.completions.create(
                        model="google/gemma-4-31b-it",
                        messages=[{"role": "system", "content": prompt}],
                        temperature=0.2,
                        max_tokens=400,
                        response_format={"type": "json_object"},
                    )
                    report_groq_success(fallback_client)
                    text = response.choices[0].message.content.strip()
                    try:
                        result = json.loads(text)
                    except json.JSONDecodeError:
                        result = {"operacion_influencia": "Error procesando JSON", "vector_manipulacion": "-", "contramedida": "-", "nivel_amenaza": "DESCONOCIDO"}
                    _cache_set(ck, result)
                    return result
                except Exception as e2:
                    report_groq_failure(fallback_client)
                    logger.error(f"[PSYOPS FALLBACK] Error: {e2}")

        # Fallback LLM local
        try:
            from ai_local import LOCAL_AI_ENABLED, query_local_llm
            if LOCAL_AI_ENABLED:
                local_res = await query_local_llm(prompt, max_tokens=400, temperature=0.2)
                if local_res:
                    try:
                        result = json.loads(local_res)
                    except json.JSONDecodeError:
                        result = {"operacion_influencia": "Error JSON local", "vector_manipulacion": "-", "contramedida": "-", "nivel_amenaza": "DESCONOCIDO"}
                    _cache_set(ck, result)
                    return result
        except Exception:
            pass

        return {"operacion_influencia": "LLM No Disponible", "vector_manipulacion": "Desconocido", "contramedida": "N/A", "nivel_amenaza": "DESCONOCIDO"}


async def analyze_news_batch(entries: list) -> list:
    """Analiza sentimiento y extrae entidades de un lote de noticias en paralelo con control de concurrencia."""
    # Máximo 5 peticiones concurrentes a la IA en este lote para evitar el efecto Thundering Herd y 429 Rate Limits
    batch_semaphore = asyncio.Semaphore(5)

    async def _analyze_single(entry):
        async with batch_semaphore:
            text = f"{entry.get('title', '')} {entry.get('summary', '')}"
            # Ejecutar sentimiento y entidades en paralelo para cada noticia
            sentiment_task = analyze_sentiment(text)
            entities_task = extract_entities(text)
            sentiment, entities = await asyncio.gather(sentiment_task, entities_task, return_exceptions=True)
            if isinstance(sentiment, Exception):
                sentiment = {"polarity": "neutral", "score": 0}
            if isinstance(entities, Exception):
                entities = {"persons": [], "organizations": [], "locations": [], "events": []}

            return {
                "title": entry.get("title", ""),
                "source": entry.get("source", ""),
                "sentiment": sentiment,
                "entities": entities,
            }

    # Procesar lote de hasta 20 noticias en paralelo bajo la restricción del semáforo
    tasks = [_analyze_single(entry) for entry in entries[:20]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]
