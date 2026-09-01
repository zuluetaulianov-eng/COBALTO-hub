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


from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(
    title="Venezuela Noticias — Standalone Portal",
    description="Portal informativo independiente y sistema CMS desacoplado.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


from fastapi.responses import FileResponse, Response


@app.get("/manifest.json")
async def serve_manifest():
    manifest_path = BASE_DIR / "static" / "manifest.json"
    if manifest_path.exists():
        return FileResponse(str(manifest_path), media_type="application/json")
    return Response(content='{"name":"Venezuela Noticias"}', media_type="application/json")


@app.get("/service-worker.js")
async def serve_sw():
    sw_path = BASE_DIR / "static" / "service-worker.js"
    if sw_path.exists():
        return FileResponse(str(sw_path), media_type="application/javascript", headers={"Cache-Control": "no-cache"})
    return Response(
        content="self.addEventListener('install', function(e) { self.skipWaiting(); }); self.addEventListener('activate', function(e) { return self.clients.claim(); });",
        media_type="application/javascript",
    )

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
