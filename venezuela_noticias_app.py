# venezuela_noticias_app.py - Servidor Autónomo e Independiente de "Venezuela Noticias"
# Permite ejecutar Venezuela Noticias sin necesidad de iniciar COBALTO HUB.
# Uso: python venezuela_noticias_app.py [--port 8080] [--host 0.0.0.0]

import argparse
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Asegurar path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import venezuela_noticias as vn  # noqa: E402
from routers.rt_venezuela_noticias import router as venezuela_noticias_router  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] venezuela_noticias: %(message)s"
)
logger = logging.getLogger("venezuela_noticias_standalone")


@asynccontextmanager
async def lifespan(app: FastAPI):
    vn.init_vn_db()
    logger.info("==================================================================")
    logger.info("  🇻🇪 VENEZUELA NOTICIAS — Portal Autónomo Iniciado Correctamente  ")
    logger.info("  • Feed Público:  http://localhost:8080/noticias                 ")
    logger.info("  • Feed RSS XML:  http://localhost:8080/noticias/rss.xml         ")
    logger.info("  • Panel CMS Admin: http://localhost:8080/vn-admin                ")
    logger.info("==================================================================")
    yield


# Inicialización de FastAPI para modo Independiente
app = FastAPI(
    title="Venezuela Noticias — Standalone Portal",
    description="Portal informativo independiente y sistema CMS desacoplado de COBALTO HUB.",
    version="1.0.0",
    lifespan=lifespan,
)

# Plantillas Jinja2
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates

# Servir archivos estáticos si existen
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root_redirect():
    """Redirecciona la raíz del puerto al portal público de noticias."""
    return RedirectResponse(url="/noticias")


# Incluir router de Venezuela Noticias
app.include_router(venezuela_noticias_router)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecutar servidor autónomo de Venezuela Noticias")
    parser.add_argument("--host", default=os.getenv("VN_HOST", "0.0.0.0"), help="Host IP")
    parser.add_argument("--port", type=int, default=int(os.getenv("VN_PORT", "8080")), help="Puerto HTTP")
    args = parser.parse_args()

    uvicorn.run("venezuela_noticias_app:app", host=args.host, port=args.port, reload=False)
