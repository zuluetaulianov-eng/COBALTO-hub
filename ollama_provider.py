import json
import logging
from typing import AsyncIterator, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

_sess: Optional[aiohttp.ClientSession] = None


def ollama_settings() -> dict:
    """Retorna la configuración Ollama desde config.py con defaults seguros (soporta Ollama Local y Ollama Cloud)."""
    try:
        import config

        host = getattr(config, "OLLAMA_HOST", "192.168.1.213")
        port = int(getattr(config, "OLLAMA_PORT", 11434))
        model = getattr(config, "OLLAMA_MODEL", "llama3.2")
        enabled = bool(getattr(config, "OLLAMA_ENABLED", True))
        timeout = float(getattr(config, "OLLAMA_TIMEOUT", 180))
        api_key = getattr(config, "OLLAMA_API_KEY", "")
    except Exception:
        host, port, model, enabled, timeout, api_key = "192.168.1.213", 11434, "llama3.2", True, 180.0, ""

    host_str = str(host).strip()
    if host_str.startswith("http://") or host_str.startswith("https://"):
        base_url = host_str.rstrip("/")
    else:
        base_url = f"http://{host_str}:{port}"

    return {
        "host": host_str,
        "port": port,
        "base_url": base_url,
        "openai_url": f"{base_url}/v1",
        "model": model,
        "enabled": enabled,
        "timeout": timeout,
        "api_key": api_key,
    }


_sess_key: Optional[tuple] = None


async def _get_session() -> aiohttp.ClientSession:
    global _sess, _sess_key
    cfg = ollama_settings()
    current_key = (cfg["base_url"], cfg.get("api_key", ""), cfg.get("timeout", 180.0))

    if _sess is not None and not _sess.closed and _sess_key != current_key:
        try:
            await _sess.close()
        except Exception:
            pass
        _sess = None

    if _sess is None or _sess.closed:
        headers = {"User-Agent": "CobaltoHub-Ollama/9.1"}
        if cfg.get("api_key"):
            headers["Authorization"] = f"Bearer {cfg['api_key']}"
        _sess = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=cfg["timeout"]),
            headers=headers,
        )
        _sess_key = current_key
    return _sess


async def close_ollama_session():
    global _sess, _sess_key
    if _sess and not _sess.closed:
        try:
            await _sess.close()
        except Exception:
            pass
    _sess = None
    _sess_key = None


async def ollama_available() -> bool:
    """Verifica si el servidor Ollama responde GET /api/tags."""
    if not ollama_settings()["enabled"]:
        return False
    try:
        session = await _get_session()
        async with session.get(ollama_settings()["base_url"] + "/api/tags", timeout=8) as resp:
            return resp.status == 200
    except Exception as ex:
        logger.warning(f"[OLLAMA] No disponible: {ex}")
        return False


async def list_ollama_models() -> List[str]:
    """Lista los modelos disponibles en el servidor Ollama."""
    try:
        session = await _get_session()
        async with session.get(ollama_settings()["base_url"] + "/api/tags", timeout=8) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception as ex:
        logger.warning(f"[OLLAMA] Error listando modelos: {ex}")
        return []


def _parse_chat_response(raw: dict) -> str:
    return raw.get("message", {}).get("content", "")


async def ollama_chat(
    messages: List[dict],
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 500,
    response_format: Optional[dict] = None,
    stream: bool = False,
) -> Optional[str]:
    """Llama al endpoint nativo de Ollama /api/chat (no streaming)."""
    cfg = ollama_settings()
    payload = {
        "model": model or cfg["model"],
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if response_format and response_format.get("type") == "json_object":
        payload["format"] = "json"
    try:
        session = await _get_session()
        async with session.post(
            cfg["base_url"] + "/api/chat", json=payload, timeout=cfg["timeout"]
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.warning(f"[OLLAMA] HTTP {resp.status}: {text[:200]}")
                return None
            raw = await resp.json()
        return _parse_chat_response(raw)
    except Exception as ex:
        logger.warning(f"[OLLAMA] Error en chat: {type(ex).__name__}: {ex}")
        return None


async def ollama_chat_stream(
    messages: List[dict],
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 500,
    response_format: Optional[dict] = None,
) -> AsyncIterator[str]:
    """Llama al endpoint nativo de Ollama /api/chat con streaming NDJSON."""
    cfg = ollama_settings()
    payload = {
        "model": model or cfg["model"],
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if response_format and response_format.get("type") == "json_object":
        payload["format"] = "json"
    session = await _get_session()
    async with session.post(cfg["base_url"] + "/api/chat", json=payload, timeout=cfg["timeout"]) as resp:
        async for line in resp.content:
            if not line.strip():
                continue
            try:
                chunk = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token
            if chunk.get("done"):
                break


class _Message:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, client: "OllamaCompatClient"):
        self._client = client

    async def create(self, **kwargs):
        return await self._client._create(**kwargs)


class _Chat:
    def __init__(self, client: "OllamaCompatClient"):
        self.completions = _Completions(client)


class OllamaCompatClient:
    """Cliente compatible con la interfaz AsyncOpenAI usada por ai_core.

    Se inserta en el pool de ai_core para que agentes, briefing, geolocalización,
    sentimiento y PsyOps funcionen contra Ollama sin reescrituras.
    """

    def __init__(self, api_key: str = "ollama", model: Optional[str] = None):
        self.api_key = api_key
        self.base_url = ollama_settings()["openai_url"]
        self.model = model or ollama_settings()["model"]
        self.chat = _Chat(self)

    async def _create(
        self,
        model: Optional[str] = None,
        messages: Optional[List[dict]] = None,
        temperature: float = 0.3,
        max_tokens: int = 500,
        response_format: Optional[dict] = None,
        stream: bool = False,
        **kwargs,
    ):
        # Si se solicita un modelo remoto/nube (ej: meta/llama-3.3-70b-instruct), usar el modelo local de Ollama (self.model)
        effective_model = self.model
        if model and not (model.startswith("meta/") or "llama-3.3" in model or "gpt-" in model or "/" in model):
            effective_model = model

        result = await ollama_chat(
            messages=messages or [],
            model=effective_model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            stream=stream,
        )
        if result is None:
            raise RuntimeError("Ollama no respondió")
        return _Response(result)


def make_ollama_client() -> Optional[OllamaCompatClient]:
    """Crea el cliente de pool si Ollama está habilitado en la configuración."""
    if not ollama_settings()["enabled"]:
        return None
    return OllamaCompatClient()
