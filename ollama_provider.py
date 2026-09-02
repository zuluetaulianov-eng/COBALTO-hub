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
    max_tokens: int = 800,
    response_format: Optional[dict] = None,
    stream: bool = False,
) -> Optional[str]:
    """Llama al endpoint de Ollama / Kobold / LMStudio local con fallbacks automáticos."""
    cfg = ollama_settings()
    target_model = model or cfg["model"]
    
    payload = {
        "model": target_model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": 1536,
        },
    }
    if response_format and response_format.get("type") == "json_object":
        payload["format"] = "json"

    try:
        session = await _get_session()
        
        # 1. Intentar endpoint nativo Ollama /api/chat
        try:
            async with session.post(
                cfg["base_url"] + "/api/chat", json=payload, timeout=cfg["timeout"]
            ) as resp:
                if resp.status == 200:
                    raw = await resp.json()
                    res = _parse_chat_response(raw)
                    if res:
                        return res
        except Exception as e1:
            logger.debug(f"[LOCAL AI] /api/chat no respondió: {e1}")

        # 2. Intentar /v1/chat/completions (OpenAI spec - LM Studio / Kobold / Ollama OpenAI API)
        openai_payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "options": {"num_ctx": 1536},
        }
        try:
            async with session.post(
                cfg["base_url"] + "/v1/chat/completions", json=openai_payload, timeout=cfg["timeout"]
            ) as resp2:
                if resp2.status == 200:
                    raw2 = await resp2.json()
                    choices = raw2.get("choices", [])
                    if choices and len(choices) > 0:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            return content
                else:
                    text2 = await resp2.text()
                    logger.warning(f"[LOCAL AI] /v1/chat/completions HTTP {resp2.status}: {text2[:150]}")
        except Exception as e2:
            logger.debug(f"[LOCAL AI] /v1/chat/completions falló: {e2}")

        # 3. Fallback KoboldCPP sin nombre de modelo rígido (previene 500 por mismatch de nombre)
        try:
            openai_payload_fallback = {
                "model": "default",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            async with session.post(
                cfg["base_url"] + "/v1/chat/completions", json=openai_payload_fallback, timeout=cfg["timeout"]
            ) as resp3:
                if resp3.status == 200:
                    raw3 = await resp3.json()
                    choices3 = raw3.get("choices", [])
                    if choices3 and len(choices3) > 0:
                        content3 = choices3[0].get("message", {}).get("content", "")
                        if content3:
                            return content3
        except Exception:
            pass

        # 4. Fallback nativo KoboldCPP /api/v1/generate (Endpoint ligero de texto crudo)
        try:
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "user").upper()
                content = msg.get("content", "")
                prompt_parts.append(f"### {role}:\n{content}")
            prompt_parts.append("### ASSISTANT:\n")
            full_prompt = "\n\n".join(prompt_parts)

            kobold_payload = {
                "prompt": full_prompt,
                "max_length": max_tokens,
                "temperature": temperature,
            }
            async with session.post(
                cfg["base_url"] + "/api/v1/generate", json=kobold_payload, timeout=cfg["timeout"]
            ) as resp4:
                if resp4.status == 200:
                    raw4 = await resp4.json()
                    results = raw4.get("results", [])
                    if results and len(results) > 0:
                        gen_text = results[0].get("text", "").strip()
                        if gen_text:
                            return gen_text
        except Exception as e4:
            logger.debug(f"[LOCAL AI] Kobold /api/v1/generate falló: {e4}")

        return None
    except Exception as ex:
        logger.warning(f"[LOCAL AI] Error general en chat: {type(ex).__name__}: {ex}")
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
