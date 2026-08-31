"""
main.py — Standalone FastAPI Application Runner for Video & CCTV Export Subsystem.
Runs independent web server, hosts Dashboard UI, and exposes REST endpoints.
"""
import argparse
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from router import video_router
from cctv_collector import snapshot_collector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[VIDEO SUBSYSTEM] Servidor de Video iniciado correctamente en puerto 8090.")
    yield
    logger.info("[VIDEO SUBSYSTEM] Cerrando recolector de fotogramas...")
    await snapshot_collector.close()

app = FastAPI(
    title="COBALTO — Subsistema Exportable de Video & CCTV",
    description="Motor independiente para ingesta, procesamiento, visión artificial y streaming de video",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount Static Files and Jinja2 Templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Include Video APIRouter
app.include_router(video_router)


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Render standalone Tactical Video Dashboard UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint for container monitoring & load balancers."""
    return {
        "status": "HEALTHY",
        "service": "COBALTO-Video-Export-Subsystem",
        "collector_active": True,
    }


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="COBALTO Standalone Video Export Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8090, help="Port to run server (default: 8090)")
    args = parser.parse_args()

    uvicorn.run("main:app", host=args.host, port=args.port, reload=True)
