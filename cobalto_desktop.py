"""
COBALTO HUB — Standalone Windows Desktop App Launcher
Ejecuta la interfaz táctica en una ventana nativa de escritorio independiente usando WebView2 (pywebview).
"""

import os
import sys
import time
import threading
import urllib.request
import uvicorn

# Configuración de codificación UTF-8 para consola de Windows
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure') and sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.platform == 'win32' and hasattr(sys.stderr, 'reconfigure') and sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Importar app FastAPI
from app import app

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8083"))

def is_server_ready(host, port):
    """Verifica si el servidor FastAPI está respondiendo solicitudes HTTP."""
    url = f"http://{host}:{port}/api/status"
    try:
        req = urllib.request.urlopen(url, timeout=1)
        return req.status == 200
    except Exception:
        return False

def run_backend():
    """Inicia el servidor FastAPI de COBALTO HUB en un hilo secundario."""
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")

def launch_desktop():
    """Inicia la aplicación de escritorio nativa usando pywebview."""
    try:
        import webview
    except ImportError:
        print("[!] ERROR: pywebview no está instalado. Instalándolo con: pip install pywebview")
        sys.exit(1)

    # Configurar Aceleración por GPU (DirectX D3D11 / ANGLE / WebGL2 / Zero-Copy) en WebView2
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        "--ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy "
        "--use-gl=angle --use-angle=d3d11 --enable-accelerated-2d-canvas "
        "--enable-features=CanvasOopRasterization"
    )

    print("==================================================")
    print(" [*] INICIANDO COBALTO HUB — TERMINAL TACTICO C4I")
    print("==================================================")
    print(f" [*] Servidor Backend en: http://{HOST}:{PORT}")

    # 1. Iniciar servidor FastAPI en hilo secundario (daemon)
    server_thread = threading.Thread(target=run_backend, daemon=True)
    server_thread.start()

    # 2. Esperar a que el servidor FastAPI esté listo
    print(" [*] Esperando respuesta del servidor backend...")
    for _ in range(30):
        if is_server_ready(HOST, PORT):
            print(" [OK] Backend sincronizado con exito.")
            break
        time.sleep(0.3)

    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, 'static', 'icons', 'cobalto.ico')
    if not os.path.exists(icon_path):
        icon_path = os.path.join(base_dir, 'static', 'icons', 'icon-512.png')

    target_url = f"http://127.0.0.1:{PORT}" if HOST in ("0.0.0.0", "127.0.0.1") else f"http://{HOST}:{PORT}"

    # 3. Crear ventana nativa de escritorio
    window = webview.create_window(
        title='COBALTO HUB v9.0 — C4I Tactical Terminal',
        url=target_url,
        width=1440,
        height=900,
        min_size=(1024, 720),
        resizable=True,
        fullscreen=False,
        confirm_close=True
    )

    # 4. Lanzar loop GUI de escritorio
    print(" [*] Abriendo ventana nativa de escritorio...")
    webview.start(icon=icon_path if os.path.exists(icon_path) else None)

if __name__ == '__main__':
    launch_desktop()
