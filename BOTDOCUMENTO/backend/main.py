import logging
from contextlib import asynccontextmanager

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("cobalto")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.middleware.auth import AuthMiddleware, auth_handler
from backend.routers.osint import router as osint_router
from backend.routers.reportes import router as reportes_router
from backend.services.docx_service import set_http_client
from backend.services.osint_service import ensure_init_async


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_init_async()
    client = httpx.AsyncClient(
        timeout=settings.image_download_timeout,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )
    set_http_client(client)
    yield
    await client.aclose()


def _build_app() -> FastAPI:
    logger.info("Construyendo aplicacion FastAPI para COBALTO")
    app = FastAPI(title="API Reportes de Patrullaje COBALTO", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.auth_enabled:
        token_val = settings.auth_token
        if token_val:

            async def verify_static_token(token: str) -> bool:
                return token == token_val

            auth_handler.set_verifier(verify_static_token)

        app.add_middleware(
            AuthMiddleware,
            exclude_paths=settings.auth_exclude_paths,
        )

    app.include_router(reportes_router)
    app.include_router(osint_router)

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok", "service": "cobalto-reportes"}

    return app


app = _build_app()


def create_app() -> FastAPI:
    return _build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,
    )
