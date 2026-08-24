"""
app_platform.py - Manejo multiplataforma para Cobalto Hub.
Elimina el Windows lock-in manteniendo compatibilidad con Linux/macOS.
"""

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


def setup_event_loop():
    """Configura el event loop de forma óptima para la plataforma actual."""
    if sys.platform == "win32":
        if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            logger.info("[PLATFORM] Event loop: Windows Proactor")
    else:
        # Linux/macOS: usar uvloop si está disponible
        try:
            import uvloop

            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            logger.info("[PLATFORM] Event loop: uvloop")
        except ImportError:
            logger.info("[PLATFORM] Event loop: asyncio default")


def silent_loop_exception_handler(loop, context):
    """Maneja errores de conexiones que se cierran abruptamente (cross-platform)."""
    msg = context.get("message", "")
    exc = context.get("exception", None)
    if exc:
        ename = type(exc).__name__
        estr = str(exc)
        if "call_connection_lost" in msg and (ename in ("ConnectionResetError", "ConnectionAbortedError")):
            return
        if "Accept failed" in msg and ename == "OSError" and "64" in estr:
            return
    loop.default_exception_handler(context)


def get_uvicorn_kwargs() -> dict:
    """Retorna kwargs óptimos para uvicorn según la plataforma y variables de entorno."""
    import os
    port = int(os.environ.get("PORT", 8083))
    kwargs = {
        "host": "0.0.0.0",
        "port": port,
        "http": "h11",
    }
    if sys.platform == "win32":
        # h11 + asyncio es la combinación más estable en Windows
        kwargs["loop"] = "asyncio"
    else:
        # httptools + uvloop en Linux/macOS ofrece mejor rendimiento
        kwargs["loop"] = "uvloop"
    return kwargs
