"""
COBALTO HUB — Standalone Windows Desktop App Launcher
Uses PyQt6 + QWebEngineView + System Tray for maximum robustness.
Closing the window minimizes to tray; service keeps running silently.
"""

import multiprocessing
import os
import sys
import io

if sys.platform == 'win32':
    multiprocessing.freeze_support()


class SafeStream(io.TextIOBase):
    def __init__(self, target):
        self.target = target

    def write(self, s):
        if not s:
            return 0
        if self.target is None:
            return len(s)
        try:
            return self.target.write(s)
        except Exception:
            try:
                enc = getattr(self.target, 'encoding', 'ascii') or 'ascii'
                safe_s = s.encode(enc, errors='replace').decode(enc, errors='replace')
                return self.target.write(safe_s)
            except Exception:
                return len(s)

    def flush(self):
        if self.target is not None and hasattr(self.target, 'flush'):
            try:
                self.target.flush()
            except Exception:
                pass


if sys.platform == 'win32':
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            sys.stdout = SafeStream(sys.stdout)
    else:
        sys.stdout = SafeStream(None)

    if sys.stderr is not None:
        try:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            sys.stderr = SafeStream(sys.stderr)
    else:
        sys.stderr = SafeStream(None)

import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)))
    APP_DIR = Path(sys.executable).parent
    proc_candidates = [
        BUNDLE_DIR / "_internal" / "PyQt6" / "Qt6" / "bin" / "QtWebEngineProcess.exe",
        BUNDLE_DIR / "PyQt6" / "Qt6" / "bin" / "QtWebEngineProcess.exe",
        APP_DIR / "_internal" / "PyQt6" / "Qt6" / "bin" / "QtWebEngineProcess.exe"
    ]
    for proc_path in proc_candidates:
        if proc_path.exists():
            os.environ["QTWEBENGINEPROCESS_PATH"] = str(proc_path)
            break
else:
    BUNDLE_DIR = Path(__file__).parent
    APP_DIR = BUNDLE_DIR

os.chdir(str(APP_DIR))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8083"))

_SINGLE_INSTANCE_MUTEX = None


def check_single_instance():
    global _SINGLE_INSTANCE_MUTEX
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            mutex = kernel32.CreateMutexW(None, False, "CobaltoHUB_SingleInstance_Mutex")
            if kernel32.GetLastError() == 183:
                return False
            _SINGLE_INSTANCE_MUTEX = mutex
            return True
        except Exception:
            pass
    return True


def is_server_ready(host=HOST, port=PORT):
    test_hosts = ["127.0.0.1", "localhost"] if host in ("0.0.0.0", "127.0.0.1") else [host]
    for h in test_hosts:
        url = f"http://{h}:{port}/api/status"
        try:
            req = urllib.request.urlopen(url, timeout=0.8)
            if req.status == 200:
                return True
        except Exception:
            pass
    return False


def clean_occupied_port(port=PORT):
    try:
        import psutil
        for proc in psutil.process_iter(['pid']):
            try:
                conns = proc.net_connections(kind='inet') if hasattr(proc, 'net_connections') else proc.connections(kind='inet')
                for conn in conns:
                    if conn.laddr.port == port and proc.pid != os.getpid():
                        proc.kill()
                        time.sleep(0.3)
            except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                pass
    except Exception:
        pass


def run_backend(dev_mode=False):
    import uvicorn
    from app import app
    log_level = "debug" if dev_mode else "warning"
    config = uvicorn.Config(app=app, host=HOST, port=PORT, log_level=log_level, loop="asyncio")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    server.run()


def run_worker():
    import asyncio
    import cobalto_worker
    try:
        asyncio.run(cobalto_worker.worker_loop())
    except Exception:
        pass


def launch_desktop(with_worker=True, dev_mode=False):
    if not check_single_instance():
        print("[!] COBALTO HUB is already running.")
        if is_server_ready():
            webbrowser.open(f"http://127.0.0.1:{PORT}")
        sys.exit(0)

    clean_occupied_port(PORT)

    print("==================================================")
    print(" [*] COBALTO HUB v9.0 - C4I TACTICAL TERMINAL")
    print("==================================================")

    if not is_server_ready():
        print(" [*] Starting FastAPI Backend thread...")
        srv_thread = threading.Thread(target=run_backend, args=(dev_mode,), daemon=True, name="CobaltoBackend")
        srv_thread.start()
    else:
        print(f" [OK] Backend already running on port {PORT}.")

    if with_worker:
        print(" [*] Starting OSINT Worker thread...")
        wrk_thread = threading.Thread(target=run_worker, daemon=True, name="CobaltoWorker")
        wrk_thread.start()

    print(" [*] Waiting for backend to be ready...")
    ready = False
    for _ in range(60):
        if is_server_ready():
            print(" [OK] Backend ready.")
            ready = True
            break
        time.sleep(0.25)

    if not ready:
        print(" [!] Backend did not respond. Opening browser as fallback.")
        webbrowser.open(f"http://127.0.0.1:{PORT}")
        while True:
            time.sleep(1)

    target_url = f"http://127.0.0.1:{PORT}" if HOST in ("0.0.0.0", "127.0.0.1") else f"http://{HOST}:{PORT}"
    _launch_qt_window(target_url)


def _launch_qt_window(url: str):
    """
    Launch COBALTO HUB in a PyQt6 QWebEngineView window with System Tray support.
    Closing the window minimizes to tray — backend services keep running.
    """
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
        from PyQt6.QtCore import Qt, QUrl
        from PyQt6.QtGui import QIcon, QAction, QCloseEvent

        if QApplication.instance() is None:
            app = QApplication(sys.argv)
        else:
            app = QApplication.instance()

        app.setApplicationName("COBALTO HUB")
        app.setApplicationDisplayName("COBALTO HUB v9.0 — C4I Tactical Terminal")
        # Prevent app from quitting when window is closed (tray mode)
        app.setQuitOnLastWindowClosed(False)

        # --- Icon ---
        icon_path = BUNDLE_DIR / "static" / "icons" / "cobalto.ico"
        if not icon_path.exists():
            icon_path = BUNDLE_DIR / "static" / "icons" / "icon-512.png"
        app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        app.setWindowIcon(app_icon)

        # --- Main Window ---
        class CobaltoWindow(QMainWindow):
            def __init__(self, tray: QSystemTrayIcon):
                super().__init__()
                self._tray = tray
                self._force_quit = False

            def closeEvent(self, event: QCloseEvent):
                if self._force_quit:
                    event.accept()
                    return
                # Minimize to tray instead of closing
                event.ignore()
                self.hide()
                self._tray.showMessage(
                    "COBALTO HUB",
                    "El servicio sigue activo en segundo plano.\nHaz clic en el icono de la bandeja para volver.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000
                )

        # --- System Tray ---
        tray = QSystemTrayIcon(app_icon, parent=None)
        tray.setToolTip("COBALTO HUB v9.0 — C4I Tactical Terminal\nServicio activo")

        tray_menu = QMenu()

        window = CobaltoWindow(tray)
        window.setWindowTitle("COBALTO HUB v9.0 — C4I Tactical Terminal")
        window.resize(1440, 900)
        window.setMinimumSize(1024, 720)
        window.setWindowIcon(app_icon)

        def show_window():
            window.show()
            window.raise_()
            window.activateWindow()

        def open_in_browser():
            webbrowser.open(url)

        def quit_app():
            window._force_quit = True
            tray.hide()
            app.quit()

        act_open = QAction("  Abrir Dashboard", tray_menu)
        act_open.triggered.connect(show_window)
        tray_menu.addAction(act_open)

        act_browser = QAction("  Abrir en Navegador", tray_menu)
        act_browser.triggered.connect(open_in_browser)
        tray_menu.addAction(act_browser)

        tray_menu.addSeparator()

        act_quit = QAction("  Detener Servicio y Salir", tray_menu)
        act_quit.triggered.connect(quit_app)
        tray_menu.addAction(act_quit)

        tray.setContextMenu(tray_menu)
        tray.activated.connect(lambda reason: show_window() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        tray.show()

        # --- WebEngine View ---
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpCacheMaximumSize(0)

        view = QWebEngineView()
        view.setPage(QWebEnginePage(profile, view))
        view.load(QUrl(url))

        window.setCentralWidget(view)
        window.show()

        print(f" [OK] Qt window opened -> {url}")
        print(" [OK] System tray active. Closing window minimizes to tray.")

        sys.exit(app.exec())

    except Exception as e:
        err_msg = f"[!] Qt window failed ({e}). Falling back to browser..."
        print(err_msg)
        try:
            with open("desktop_error.log", "a", encoding="utf-8") as f:
                import traceback
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {err_msg}\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        webbrowser.open(url)
        while True:
            time.sleep(1)


def main():
    multiprocessing.freeze_support()

    if "--server" in sys.argv:
        run_backend(dev_mode="--dev" in sys.argv)
        return

    if "--worker" in sys.argv:
        import cobalto_worker
        cobalto_worker.main()
        return

    if "--control-panel" in sys.argv or "--gui" in sys.argv:
        import cobalto_gui_launcher
        cobalto_gui_launcher.launch_control_panel()
        return

    if "--tui" in sys.argv or "--cli" in sys.argv:
        import cobalto_launcher
        cobalto_launcher.main()
        return

    dev_mode = "--dev" in sys.argv
    with_worker = "--no-worker" not in sys.argv
    launch_desktop(with_worker=with_worker, dev_mode=dev_mode)


if __name__ == '__main__':
    main()
