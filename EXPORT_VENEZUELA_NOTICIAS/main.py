# main.py - Servidor Autónomo de Venezuela Noticias
# Repositorio Independiente GitHub

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

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from router import router as venezuela_noticias_router  # noqa: E402

import venezuela_noticias as vn  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] venezuela_noticias: %(message)s"
)
logger = logging.getLogger("venezuela_noticias")


@asynccontextmanager
async def lifespan(app: FastAPI):
    vn.init_vn_db()
    port = os.getenv("VN_PORT", "8085")
    logger.info("==================================================================")
    logger.info("  🇻🇪 VENEZUELA NOTICIAS — Portal Autónomo Iniciado Correctamente  ")
    logger.info(f"  • Feed Público:  http://localhost:{port}/noticias               ")
    logger.info(f"  • Feed RSS XML:  http://localhost:{port}/noticias/rss.xml       ")
    logger.info(f"  • Panel CMS Admin: http://localhost:{port}/vn-admin              ")
    logger.info("==================================================================")
    yield


from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(
    title="Venezuela Noticias — Standalone Portal",
    description="Portal informativo independiente y sistema CMS desacoplado.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates

class CachedStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", CachedStaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/noticias")


app.include_router(venezuela_noticias_router)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecutar servidor autónomo de Venezuela Noticias")
    parser.add_argument("--host", default=os.getenv("VN_HOST", "0.0.0.0"), help="Host IP")
    parser.add_argument("--port", type=int, default=int(os.getenv("VN_PORT", "8085")), help="Puerto HTTP")
    args = parser.parse_args()

    uvicorn.run("main:app", host=args.host, port=args.port, reload=False)
