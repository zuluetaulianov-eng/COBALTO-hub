#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cobalto_gui_launcher.py — Centro de Control Gráfico de COBALTO Hub
==================================================================
Interfaz gráfica premium (Tkinter con estética cyberpunk dark/neon)
que permite el monitoreo del sistema en vivo y el control granular
de los procesos (iniciar/detener el servidor web y los extractores
en el orden que el operador prefiera).

Soporta fallback automático a TUI (Modo Consola) en entornos headless.
"""

import multiprocessing
import os
import sys

if sys.platform == 'win32':
    multiprocessing.freeze_support()

import io

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

import socket
import subprocess
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path


def is_server_ready(host="127.0.0.1", port=8083):
    """Verifica si el servidor FastAPI está respondiendo solicitudes HTTP."""
    url = f"http://{host}:{port}/api/status"
    try:
        req = urllib.request.urlopen(url, timeout=0.8)
        return req.status == 200
    except Exception:
        return False

# Cargar dotenv para configuraciones del puerto, etc.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent
os.chdir(str(BASE_DIR))

# Intentar importar psutil para métricas del sistema en tiempo real
HAS_PSUTIL = False
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    pass

# Rutas de los logs
WORKER_LOG = BASE_DIR / "worker.log"
SERVER_LOG = BASE_DIR / "server.log"

# Fallback a Tkinter
HAS_GUI = False
try:
    import tkinter as tk
    from tkinter import messagebox, ttk
    from tkinter.scrolledtext import ScrolledText
    HAS_GUI = True
except ImportError:
    pass


class CobaltoEngine:
    """Orquestador de subprocesos para Servidor, Worker y Ventana Nativa."""
    def __init__(self):
        self.server_process = None
        self.worker_process = None
        self.desktop_process = None
        self.start_time = time.time()

        # Variables de estado esperado (para el Watchdog)
        self.expected_server_state = False
        self.expected_worker_state = False
        self.last_server_restart = 0
        self.last_worker_restart = 0

    def is_server_running(self):
        if self.server_process is not None and self.server_process.poll() is None:
            return True
        port = int(os.getenv("PORT", "8083"))
        return is_server_ready("127.0.0.1", port)

    def is_worker_running(self):
        return self.worker_process is not None and self.worker_process.poll() is None

    def start_server(self, dev_mode=False):
        if self.is_server_running():
            return False

        # Prevenir error [Errno 10048] (puerto ocupado) matando procesos zombies en el puerto
        if HAS_PSUTIL:
            port = int(os.getenv("PORT", "8083"))
            try:
                for proc in psutil.process_iter(['pid']):
                    try:
                        for conn in proc.connections(kind='inet'):
                            if conn.laddr.port == port:
                                proc.kill()
                                time.sleep(0.5)
                    except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                        pass
            except Exception:
                pass

        if getattr(sys, 'frozen', False):
            args = [sys.executable, "--server"]
        else:
            args = [sys.executable, "app.py"]
        if dev_mode:
            args.append("--dev")

        self.expected_server_state = True

        # Rotación básica: Si el log existe y pesa más de 5MB, lo archivamos
        if SERVER_LOG.exists():
            try:
                if SERVER_LOG.stat().st_size > 5 * 1024 * 1024:
                    SERVER_LOG.rename(SERVER_LOG.with_name(f"server_{int(time.time())}.log"))
                else:
                    SERVER_LOG.unlink()
            except Exception:
                pass

        log_file = open(str(SERVER_LOG), "w", encoding="utf-8")
        self.server_process = subprocess.Popen(
            args,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR)
        )
        return True

    def stop_server(self):
        self.expected_server_state = False
        if not self.is_server_running():
            return False

        proc = self.server_process
        try:
            if os.name == 'nt':
                # Graceful attempt (sin /F)
                subprocess.call(["taskkill", "/PID", str(proc.pid), "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    proc.wait(timeout=10) # 10 segundos de gracia
                except subprocess.TimeoutExpired:
                    # Force kill si no obedece
                    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            pass
        self.server_process = None
        return True

    def start_worker(self):
        if self.is_worker_running():
            return False

        self.expected_worker_state = True

        # Rotación básica: Si el log existe y pesa más de 5MB, lo archivamos
        if WORKER_LOG.exists():
            try:
                if WORKER_LOG.stat().st_size > 5 * 1024 * 1024:
                    WORKER_LOG.rename(WORKER_LOG.with_name(f"worker_{int(time.time())}.log"))
                else:
                    WORKER_LOG.unlink()
            except Exception:
                pass

        if getattr(sys, 'frozen', False):
            args = [sys.executable, "--worker"]
        else:
            args = [sys.executable, "cobalto_worker.py"]
        log_file = open(str(WORKER_LOG), "w", encoding="utf-8")
        self.worker_process = subprocess.Popen(
            args,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR)
        )
        return True

    def stop_worker(self):
        self.expected_worker_state = False
        if not self.is_worker_running():
            return False

        proc = self.worker_process
        try:
            if os.name == 'nt':
                # Graceful attempt (sin /F)
                subprocess.call(["taskkill", "/PID", str(proc.pid), "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    proc.wait(timeout=10) # 10 segundos de gracia
                except subprocess.TimeoutExpired:
                    # Force kill si no obedece
                    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            pass
        self.worker_process = None
        return True

    def is_desktop_running(self):
        return self.desktop_process is not None and self.desktop_process.poll() is None

    def start_desktop(self):
        if self.is_desktop_running():
            return False

        if getattr(sys, 'frozen', False):
            args = [sys.executable, "--desktop"]
        else:
            args = [sys.executable, "cobalto_gui_launcher.py", "--desktop"]

        self.desktop_process = subprocess.Popen(
            args,
            cwd=str(BASE_DIR)
        )
        return True

    def stop_desktop(self):
        if not self.is_desktop_running():
            return False
        proc = self.desktop_process
        try:
            if os.name == 'nt':
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                proc.kill()
        except Exception:
            pass
        self.desktop_process = None
        return True

    def stop_all(self):
        self.stop_desktop()
        self.stop_server()
        self.stop_worker()

    def get_proc_metrics(self, proc):
        """Obtiene CPU y Memoria RAM de un proceso usando psutil."""
        if not proc or proc.poll() is not None or not HAS_PSUTIL:
            return 0.0, 0.0
        try:
            if not hasattr(proc, '_psutil_proc'):
                proc._psutil_proc = psutil.Process(proc.pid)
            p = proc._psutil_proc
            cpu = p.cpu_percent(interval=None)
            mem = p.memory_info().rss / (1024 * 1024)  # en MB
            return cpu, mem
        except Exception:
            return 0.0, 0.0


# ── INTERFAZ GRÁFICA (CYBERPUNK GUI) ──
class CobaltoGUI:
    def __init__(self, engine):
        self.engine = engine
        self.root = tk.Tk()
        self.root.title("COBALTO HUB v9.0 — Tactical Control Center")
        self.root.geometry("900x700")
        self.root.configure(bg="#060608")

        # Configurar icono o fallback
        try:
            ico_file = os.path.join(BASE_DIR, "static", "icons", "cobalto.ico")
            if os.path.exists(ico_file):
                self.root.iconbitmap(ico_file)
            else:
                self.root.iconbitmap("favicon.ico")
        except Exception:
            pass

        # Paleta de colores Neon Cyberpunk
        self.c_bg = "#060608"
        self.c_card = "#0f0f15"
        self.c_border = "#1a1a24"
        self.c_cyan = "#00e5ff"
        self.c_green = "#00ffaa"
        self.c_red = "#ff3366"
        self.c_yellow = "#ffcc00"
        self.c_white = "#ffffff"
        self.c_gray = "#888899"

        # Aplicar estilos globales de ttk
        self.style = ttk.Style()
        self.style.theme_use('default')
        self.style.configure(".", background=self.c_bg, foreground=self.c_white)

        # Variables dinámicas
        self.web_port = os.getenv("PORT", "8083")

        self.build_ui()
        self.last_log_pos_worker = 0
        self.last_log_pos_server = 0

        # Iniciar ciclo de actualización en tiempo real (cada 1s)
        self.update_loop()

    def build_ui(self):
        # Header Táctico
        header_frame = tk.Frame(self.root, bg=self.c_card, height=70, bd=1, relief="ridge", highlightbackground=self.c_cyan, highlightcolor=self.c_cyan, highlightthickness=1)
        header_frame.pack(fill="x", padx=15, pady=10)

        lbl_title = tk.Label(header_frame, text="COBALTO HUB v9.0", font=("Consolas", 18, "bold"), fg=self.c_cyan, bg=self.c_card)
        lbl_title.pack(side="left", padx=20, pady=10)

        self.lbl_uptime = tk.Label(header_frame, text="UPTIME: 00:00:00", font=("Consolas", 10, "bold"), fg=self.c_gray, bg=self.c_card)
        self.lbl_uptime.pack(side="right", padx=20, pady=15)

        # Contenedor central (2 Columnas)
        main_pane = tk.Frame(self.root, bg=self.c_bg)
        main_pane.pack(fill="both", expand=True, padx=15)

        # Columna Izquierda: Monitoreo de Recursos del Sistema
        left_col = tk.Frame(main_pane, bg=self.c_bg, width=350)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Panel de Métricas Generales
        sys_frame = tk.LabelFrame(left_col, text=" [ MONITOREO GENERAL DEL SISTEMA ] ", font=("Consolas", 10, "bold"), fg=self.c_cyan, bg=self.c_card, bd=1, relief="solid")
        sys_frame.pack(fill="x", ipady=15, pady=(0, 10))

        tk.Label(sys_frame, text="CPU General:", font=("Consolas", 10), fg=self.c_white, bg=self.c_card).pack(anchor="w", padx=20, pady=(10, 2))
        self.canvas_cpu = tk.Canvas(sys_frame, width=280, height=18, bg="#0d0d13", highlightthickness=0)
        self.canvas_cpu.pack(anchor="w", padx=20)
        self.lbl_cpu_text = tk.Label(sys_frame, text="0.0%", font=("Consolas", 9, "bold"), fg=self.c_cyan, bg=self.c_card)
        self.lbl_cpu_text.pack(anchor="w", padx=20)

        tk.Label(sys_frame, text="RAM General:", font=("Consolas", 10), fg=self.c_white, bg=self.c_card).pack(anchor="w", padx=20, pady=(10, 2))
        self.canvas_ram = tk.Canvas(sys_frame, width=280, height=18, bg="#0d0d13", highlightthickness=0)
        self.canvas_ram.pack(anchor="w", padx=20)
        self.lbl_ram_text = tk.Label(sys_frame, text="0.0%", font=("Consolas", 9, "bold"), fg=self.c_cyan, bg=self.c_card)
        self.lbl_ram_text.pack(anchor="w", padx=20)

        # Panel C4i Bases de Datos
        db_frame = tk.LabelFrame(left_col, text=" [ NÚCLEO DE DATOS C4i ] ", font=("Consolas", 10, "bold"), fg=self.c_cyan, bg=self.c_card, bd=1, relief="solid")
        db_frame.pack(fill="x", ipady=5, pady=(0, 10))

        db_container = tk.Frame(db_frame, bg=self.c_card)
        db_container.pack(fill="x", padx=15, pady=5)

        # Contenedor para la lista de bases de datos
        db_list_frame = tk.Frame(db_container, bg=self.c_card)
        db_list_frame.pack(side="left", fill="both", expand=True)

        self.db_status_labels = {}
        for db_name, port in [("PostgreSQL", 5432), ("Redis", 6379), ("Elasticsearch", 9200), ("Neo4j", 7687)]:
            row = tk.Frame(db_list_frame, bg=self.c_card)
            row.pack(fill="x", pady=2)

            lbl_indicator = tk.Label(row, text="●", font=("Consolas", 10), fg=self.c_gray, bg=self.c_card)
            lbl_indicator.pack(side="left")

            tk.Label(row, text=f"{db_name} (:{port})", font=("Consolas", 9), fg=self.c_white, bg=self.c_card).pack(side="left", padx=5)
            self.db_status_labels[db_name] = {"label": lbl_indicator, "port": port}

        # Botón lateral de Auto-Ignición Docker
        btn_docker = tk.Button(db_container, text="ARRANCAR\nDOCKER", font=("Consolas", 8, "bold"), bg="#0a2a4a", fg=self.c_cyan, bd=1, relief="solid", cursor="hand2", command=self.on_start_docker)
        btn_docker.pack(side="right", padx=10, pady=10)

        # Panel de Controles Granulares de Procesos
        ctrl_frame = tk.LabelFrame(left_col, text=" [ PANEL DE CONTROL DE PROCESOS ] ", font=("Consolas", 10, "bold"), fg=self.c_cyan, bg=self.c_card, bd=1, relief="solid")
        ctrl_frame.pack(fill="both", expand=True)

        # CONTROL SERVIDOR WEB
        server_sec = tk.Frame(ctrl_frame, bg=self.c_card)
        server_sec.pack(fill="x", padx=15, pady=10)

        self.indicator_server = tk.Label(server_sec, text="●", font=("Consolas", 14), fg=self.c_red, bg=self.c_card)
        self.indicator_server.pack(side="left")

        tk.Label(server_sec, text=f"SERVIDOR WEB (Puerto {self.web_port})", font=("Consolas", 10, "bold"), fg=self.c_white, bg=self.c_card).pack(side="left", padx=5)

        server_btn_frame = tk.Frame(ctrl_frame, bg=self.c_card)
        server_btn_frame.pack(fill="x", padx=20)

        self.btn_start_server = tk.Button(server_btn_frame, text="INICIAR WEB", font=("Consolas", 8, "bold"), bg=self.c_green, fg="#000000", activebackground=self.c_green, bd=0, width=12, command=self.on_start_server)
        self.btn_start_server.pack(side="left", padx=2)

        self.btn_stop_server = tk.Button(server_btn_frame, text="DETENER WEB", font=("Consolas", 8, "bold"), bg=self.c_red, fg=self.c_white, activebackground=self.c_red, bd=0, width=12, command=self.on_stop_server)
        self.btn_stop_server.pack(side="left", padx=2)

        self.lbl_srv_metrics = tk.Label(ctrl_frame, text="CPU: 0% │ RAM: 0.0 MB", font=("Consolas", 9), fg=self.c_gray, bg=self.c_card)
        self.lbl_srv_metrics.pack(anchor="w", padx=20, pady=(2, 10))

        # CONTROL WORKER EXTRACTOR
        worker_sec = tk.Frame(ctrl_frame, bg=self.c_card)
        worker_sec.pack(fill="x", padx=15, pady=10)

        self.indicator_worker = tk.Label(worker_sec, text="●", font=("Consolas", 14), fg=self.c_red, bg=self.c_card)
        self.indicator_worker.pack(side="left")

        tk.Label(worker_sec, text="EXTRACTOR OSINT (Worker)", font=("Consolas", 10, "bold"), fg=self.c_white, bg=self.c_card).pack(side="left", padx=5)

        worker_btn_frame = tk.Frame(ctrl_frame, bg=self.c_card)
        worker_btn_frame.pack(fill="x", padx=20)

        self.btn_start_worker = tk.Button(worker_btn_frame, text="INICIAR OSINT", font=("Consolas", 8, "bold"), bg=self.c_green, fg="#000000", activebackground=self.c_green, bd=0, width=12, command=self.on_start_worker)
        self.btn_start_worker.pack(side="left", padx=2)

        self.btn_stop_worker = tk.Button(worker_btn_frame, text="DETENER OSINT", font=("Consolas", 8, "bold"), bg=self.c_red, fg=self.c_white, activebackground=self.c_red, bd=0, width=12, command=self.on_stop_worker)
        self.btn_stop_worker.pack(side="left", padx=2)

        self.lbl_wrk_metrics = tk.Label(ctrl_frame, text="CPU: 0% │ RAM: 0.0 MB", font=("Consolas", 9), fg=self.c_gray, bg=self.c_card)
        self.lbl_wrk_metrics.pack(anchor="w", padx=20, pady=(2, 10))

        # KILL SWITCHES
        kill_sec = tk.Frame(ctrl_frame, bg=self.c_card)
        kill_sec.pack(fill="x", padx=15, pady=5)

        tk.Label(kill_sec, text="KILL SWITCHES (MÓDULOS):", font=("Consolas", 8, "bold"), fg=self.c_cyan, bg=self.c_card).pack(anchor="w", pady=(0, 5))

        # Inicializar estado desde la base de datos para los Kill Switches
        init_osint, init_social, init_nlp = True, True, True
        try:
            import database
            initial_data = database.get_system_settings("dynamic_config") or {}
            if "MODULE_OSINT_ACTIVE" in initial_data:
                init_osint = initial_data["MODULE_OSINT_ACTIVE"]
            if "MODULE_SOCIAL_ACTIVE" in initial_data:
                init_social = initial_data["MODULE_SOCIAL_ACTIVE"]
            if "MODULE_NLP_ACTIVE" in initial_data:
                init_nlp = initial_data["MODULE_NLP_ACTIVE"]
        except Exception:
            pass

        self.var_osint = tk.BooleanVar(value=init_osint)
        self.var_social = tk.BooleanVar(value=init_social)
        self.var_nlp = tk.BooleanVar(value=init_nlp)

        def update_kill_switches():
            os.environ["MODULE_OSINT_ACTIVE"] = "true" if self.var_osint.get() else "false"
            os.environ["MODULE_SOCIAL_ACTIVE"] = "true" if self.var_social.get() else "false"
            os.environ["MODULE_NLP_ACTIVE"] = "true" if self.var_nlp.get() else "false"

            # Sincronizar dinámicamente con la base de datos (background thread)
            def _sync_config():
                try:
                    import json
                    from pathlib import Path

                    import config
                    import database

                    data = database.get_system_settings("dynamic_config")
                    if not data:
                        cfg_path = Path("config_dynamic.json")
                        if cfg_path.exists():
                            with open(cfg_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                        else:
                            data = {}

                    data["MODULE_OSINT_ACTIVE"] = self.var_osint.get()
                    data["MODULE_SOCIAL_ACTIVE"] = self.var_social.get()
                    data["MODULE_NLP_ACTIVE"] = self.var_nlp.get()

                    config.save_dynamic_config(data)

                    # Notificar en consola grafica
                    def _log_success():
                        self.txt_logs.config(state="normal")
                        self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [SISTEMA] Kill Switches sincronizados en Backend.\n", "system")
                        if self.auto_scroll_var.get():
                            self.txt_logs.see("end")
                    self.root.after(0, _log_success)
                except Exception as exc:
                    err_msg = str(exc)
                    def _log_err():
                        self.txt_logs.config(state="normal")
                        self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] Sincronización Kill Switch: {err_msg}\n", "system")
                    self.root.after(0, _log_err)

            threading.Thread(target=_sync_config, daemon=True).start()

        chk_osint = tk.Checkbutton(kill_sec, text="OSINT", variable=self.var_osint, font=("Consolas", 8), bg=self.c_card, fg="#00e5ff", selectcolor="#1a1a24", activebackground=self.c_card, command=update_kill_switches)
        chk_osint.pack(side="left", padx=5)

        chk_social = tk.Checkbutton(kill_sec, text="SOCIAL", variable=self.var_social, font=("Consolas", 8), bg=self.c_card, fg="#b388ff", selectcolor="#1a1a24", activebackground=self.c_card, command=update_kill_switches)
        chk_social.pack(side="left", padx=5)

        chk_nlp = tk.Checkbutton(kill_sec, text="NLP/IA", variable=self.var_nlp, font=("Consolas", 8), bg=self.c_card, fg="#FF2D55", selectcolor="#1a1a24", activebackground=self.c_card, command=update_kill_switches)
        chk_nlp.pack(side="left", padx=5)

        # Omitimos llamar a update_kill_switches() inicial para no disparar el hilo de guardado
        # en el arranque innecesariamente, ya que los valores vienen de la DB.
        os.environ["MODULE_OSINT_ACTIVE"] = "true" if self.var_osint.get() else "false"
        os.environ["MODULE_SOCIAL_ACTIVE"] = "true" if self.var_social.get() else "false"
        os.environ["MODULE_NLP_ACTIVE"] = "true" if self.var_nlp.get() else "false"

        # CONTROLES GLOBALES
        global_btn_frame = tk.Frame(ctrl_frame, bg="#0d0d12", bd=1, relief="solid")
        global_btn_frame.pack(fill="x", padx=15, pady=15, ipady=5)

        tk.Label(global_btn_frame, text="ACCIONES GLOBALES:", font=("Consolas", 8, "bold"), fg=self.c_cyan, bg="#0d0d12").pack(anchor="w", padx=10, pady=5)

        btn_start_all = tk.Button(global_btn_frame, text="INICIAR TODO", font=("Consolas", 8, "bold"), bg=self.c_cyan, fg="#000000", activebackground=self.c_cyan, bd=0, width=12, command=self.on_start_all)
        btn_start_all.pack(side="left", padx=10)

        btn_stop_all = tk.Button(global_btn_frame, text="APAGAR TODO", font=("Consolas", 8, "bold"), bg=self.c_red, fg=self.c_white, activebackground=self.c_red, bd=0, width=12, command=self.on_stop_all)
        btn_stop_all.pack(side="left", padx=5)

        btn_open_web = tk.Button(global_btn_frame, text="🖥️ TERMINAL TÁCTICO", font=("Consolas", 8, "bold"), bg="#ffcc00", fg="#000000", activebackground="#ffdd33", bd=0, width=18, command=self.open_native_window)
        btn_open_web.pack(side="right", padx=10)

        # Columna Derecha: Visor de Logs Consolidado
        right_col = tk.Frame(main_pane, bg=self.c_bg)
        right_col.pack(side="right", fill="both", expand=True)

        logs_frame = tk.LabelFrame(right_col, text=" [ FEED DE INTELIGENCIA Y SISTEMA (LOGS) ] ", font=("Consolas", 10, "bold"), fg=self.c_cyan, bg=self.c_card, bd=1, relief="solid")
        logs_frame.pack(fill="both", expand=True)

        self.txt_logs = ScrolledText(logs_frame, bg="#08080c", fg="#00ffaa", font=("Consolas", 9), insertbackground=self.c_cyan, bd=0, highlightthickness=0)
        self.txt_logs.pack(fill="both", expand=True, padx=5, pady=5)

        # Tags de color para diferenciar logs del worker y servidor
        self.txt_logs.tag_config("worker", foreground=self.c_green)
        self.txt_logs.tag_config("server", foreground=self.c_cyan)
        self.txt_logs.tag_config("system", foreground=self.c_yellow)

        self.txt_logs.insert("end", "[SISTEMA] Lanzador Gráfico Inicializado.\n", "system")

        # Botones de control del Visor de Logs
        logs_ctrl_frame = tk.Frame(logs_frame, bg=self.c_card)
        logs_ctrl_frame.pack(fill="x", side="bottom", padx=10, pady=(0, 5))

        # Variable para controlar el Auto-Scroll
        self.auto_scroll_var = tk.BooleanVar(value=True)
        chk_scroll = tk.Checkbutton(
            logs_ctrl_frame,
            text="AUTO-SCROLL",
            variable=self.auto_scroll_var,
            font=("Consolas", 8),
            bg=self.c_card,
            fg=self.c_white,
            activebackground=self.c_card,
            activeforeground=self.c_white,
            selectcolor="#1a1a24"
        )
        chk_scroll.pack(side="right", padx=10)

        btn_clear = tk.Button(
            logs_ctrl_frame,
            text="LIMPIAR CONSOLA",
            font=("Consolas", 8, "bold"),
            bg="#1a1a24",
            fg=self.c_cyan,
            activebackground="#2a2a34",
            bd=0,
            padx=10,
            pady=3,
            command=self.clear_console_logs
        )
        btn_clear.pack(side="left", padx=5)

        btn_view_errors = tk.Button(
            logs_ctrl_frame,
            text="VER REGISTRO DE FALLAS",
            font=("Consolas", 8, "bold"),
            bg="#1a1a24",
            fg=self.c_yellow,
            activebackground="#2a2a34",
            bd=0,
            padx=10,
            pady=3,
            command=self.open_failures_log
        )
        btn_view_errors.pack(side="left", padx=5)

    def on_start_docker(self):
        def _log_to_gui(msg, level="system"):
            self.txt_logs.config(state="normal")
            self.txt_logs.insert("end", msg, level)
            if self.auto_scroll_var.get():
                self.txt_logs.see("end")

        def _show_warning(title, msg):
            messagebox.showwarning(title, msg)

        def _run():
            try:
                # Comprobar si existe el comando docker
                subprocess.run(["docker", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.root.after(0, lambda: _log_to_gui(f"\n[{datetime.now().strftime('%H:%M:%S')}] [SISTEMA] Motor Docker detectado. Iniciando clúster C4i...\n"))

                # Ejecutar docker compose up -d
                subprocess.run(["docker-compose", "up", "-d"], check=True, cwd=str(BASE_DIR))
                self.root.after(0, lambda: _log_to_gui(f"[{datetime.now().strftime('%H:%M:%S')}] [SISTEMA] Servicios de datos C4i encendidos exitosamente.\n"))
            except FileNotFoundError:
                self.root.after(0, lambda: _show_warning("Docker No Detectado", "El comando 'docker' no se encuentra en este sistema operativo.\n\nEl sistema ejecutará automáticamente el Fallback a SQLite/Local JSON. No es crítico, pero limitará funciones avanzadas."))
            except subprocess.CalledProcessError as exc:
                err_msg = str(exc)
                self.root.after(0, lambda: _log_to_gui(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] Fallo al iniciar Docker: {err_msg}\n"))

        threading.Thread(target=_run, daemon=True).start()

    def draw_bar(self, canvas, percentage, color):
        canvas.delete("all")
        width = 280
        height = 18
        # Fondo
        canvas.create_rectangle(0, 0, width, height, fill="#12121e", outline="")
        # Relleno de porcentaje
        fill_width = int(width * (percentage / 100))
        if fill_width > 0:
            canvas.create_rectangle(0, 0, fill_width, height, fill=color, outline="")

    def on_start_server(self):
        # Preguntar si desea iniciar modo dev o producción
        if self.engine.is_server_running():
            return

        # Caja de diálogo cyberpunk para modo
        top = tk.Toplevel(self.root)
        top.title("Modo de Lanzamiento Web")
        top.geometry("320x150")
        top.configure(bg=self.c_card)
        top.transient(self.root)
        top.grab_set()

        lbl = tk.Label(top, text="Seleccione el modo del Servidor FastAPI:", font=("Consolas", 10, "bold"), fg=self.c_white, bg=self.c_card)
        lbl.pack(pady=20)

        btn_frame = tk.Frame(top, bg=self.c_card)
        btn_frame.pack(fill="x")

        def start_normal():
            self.last_log_pos_server = 0
            self.engine.start_server(dev_mode=False)
            self.txt_logs.insert("end", f"\n[{datetime.now().strftime('%H:%M:%S')}] ====================================================\n", "system")
            self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [SYSTEM] Inciando Servidor Web (Producción)\n", "system")
            self.txt_logs.see("end")
            top.destroy()

        def start_dev():
            self.last_log_pos_server = 0
            self.engine.start_server(dev_mode=True)
            self.txt_logs.insert("end", f"\n[{datetime.now().strftime('%H:%M:%S')}] ====================================================\n", "system")
            self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [SYSTEM] Inciando Servidor Web (Desarrollo --dev)\n", "system")
            self.txt_logs.see("end")
            top.destroy()

        tk.Button(btn_frame, text="PRODUCCIÓN", font=("Consolas", 9, "bold"), bg=self.c_cyan, fg="#000000", bd=0, width=12, command=start_normal).pack(side="left", padx=15)
        tk.Button(btn_frame, text="DESARROLLO", font=("Consolas", 9, "bold"), bg=self.c_yellow, fg="#000000", bd=0, width=12, command=start_dev).pack(side="right", padx=15)

    def on_stop_server(self):
        if self.engine.stop_server():
            self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [SYSTEM] Servidor Web Detenido.\n", "system")

    def on_start_worker(self):
        self.last_log_pos_worker = 0
        if self.engine.start_worker():
            self.txt_logs.insert("end", f"\n[{datetime.now().strftime('%H:%M:%S')}] ====================================================\n", "system")
            self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [SYSTEM] Iniciando Extractor OSINT...\n", "system")
            self.txt_logs.see("end")

    def on_stop_worker(self):
        if self.engine.stop_worker():
            self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [SYSTEM] Extractor OSINT Detenido.\n", "system")

    def on_start_all(self):
        self.on_start_worker()
        self.root.after(1000, lambda: self.engine.start_server(dev_mode=False))
        self.root.after(2500, self.open_native_window)

    def open_native_window(self):
        if not self.engine.is_server_running():
            self.engine.start_server(dev_mode=False)

        if self.engine.is_desktop_running():
            return

        if self.engine.start_desktop():
            self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [SYSTEM] Abriendo terminal nativo C4I (PyWebView)...\n", "system")
            self.txt_logs.see("end")

    def on_stop_all(self):
        self.engine.stop_all()
        self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [SYSTEM] Todos los procesos detenidos globalmente.\n", "system")

    def clear_console_logs(self):
        self.txt_logs.config(state="normal")
        self.txt_logs.delete("1.0", "end")
        self.txt_logs.insert("end", "[SISTEMA] Consola de logs limpia.\n", "system")
        self.txt_logs.see("end")

    def open_failures_log(self):
        failures_path = Path("failures.log")
        if not failures_path.exists():
            messagebox.showinfo("Registro de Fallas", "No se han detectado errores ni fallas registradas aún. ¡Sistema saludable!")
            return

        try:
            if os.name == 'nt':
                os.startfile(str(failures_path))
            else:
                subprocess.call(["xdg-open", str(failures_path)])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el registro de fallas: {e}")

    def log_error_to_file(self, origin, line):
        try:
            with open("failures.log", "a", encoding="utf-8") as err_f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                err_f.write(f"[{timestamp}] [{origin}] {line.strip()}\n")
        except Exception:
            pass

    def read_live_logs(self):
        """Lee líneas frescas de los logs de forma no bloqueante y las añade al Text box."""
        # Prevenir desbordamiento de memoria de Tkinter truncando si pasa las 3000 lineas
        if int(self.txt_logs.index('end-1c').split('.')[0]) > 3000:
            self.txt_logs.config(state="normal")
            self.txt_logs.delete("1.0", "1500.0")

        # Logs de Worker
        if WORKER_LOG.exists():
            try:
                with open(WORKER_LOG, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(self.last_log_pos_worker)
                    new_lines = f.readlines()
                    if new_lines:
                        self.txt_logs.config(state="normal")
                        for line in new_lines:
                            self.txt_logs.insert("end", f"[OSINT] {line}", "worker")
                            if any(x in line for x in ["ERROR", "Traceback", "Exception", "Fail", "FALLÓ", "error"]):
                                self.log_error_to_file("OSINT-WORKER", line)
                        if self.auto_scroll_var.get():
                            self.txt_logs.see("end")
                    self.last_log_pos_worker = f.tell()
            except Exception:
                pass

        # Logs de Server
        if SERVER_LOG.exists():
            try:
                with open(SERVER_LOG, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(self.last_log_pos_server)
                    new_lines = f.readlines()
                    if new_lines:
                        self.txt_logs.config(state="normal")
                        for line in new_lines:
                            self.txt_logs.insert("end", f"[WEB] {line}", "server")
                            if any(x in line for x in ["ERROR", "Traceback", "Exception", "Fail", "FALLÓ", "error"]):
                                self.log_error_to_file("WEB-SERVER", line)
                        if self.auto_scroll_var.get():
                            self.txt_logs.see("end")
                    self.last_log_pos_server = f.tell()
            except Exception:
                pass

    def update_loop(self):
        """Bucle recurrente que actualiza los indicadores gráficos de la UI."""
        # 1. Uptime
        uptime = str(datetime.now() - datetime.fromtimestamp(self.engine.start_time)).split('.')[0]
        self.lbl_uptime.config(text=f"UPTIME: {uptime}")

        # 2. Métricas del Sistema
        if HAS_PSUTIL:
            try:
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                self.draw_bar(self.canvas_cpu, cpu, self.c_cyan)
                self.draw_bar(self.canvas_ram, ram, self.c_cyan)
                self.lbl_cpu_text.config(text=f"{cpu}%")
                self.lbl_ram_text.config(text=f"{ram}%")
            except Exception:
                pass

        # 2.5 Estado de Bases de Datos C4i
        # Chequeo rápido por socket para no bloquear la UI
        def check_port(port):
            try:
                with socket.create_connection(("localhost", port), timeout=0.1):
                    return True
            except OSError:
                return False

        # Ejecutar el chequeo en un hilo ligero (para evitar micro-cortes)
        def refresh_db_status():
            for db_name, data in self.db_status_labels.items():
                is_up = check_port(data["port"])
                color = self.c_green if is_up else self.c_red
                # Actualizar GUI de forma segura (Tkinter permite configuraciones simples de color desde hilos paralelos pero es riesgoso, mejor root.after)
                self.root.after(0, lambda d=data["label"], c=color: d.config(fg=c))

        threading.Thread(target=refresh_db_status, daemon=True).start()

        # 3. Estado de Servidor Web
        if self.engine.is_server_running():
            self.indicator_server.config(fg=self.c_green)
            self.btn_start_server.config(state="disabled")
            self.btn_stop_server.config(state="normal")
            srv_cpu, srv_mem = self.engine.get_proc_metrics(self.engine.server_process)
            self.lbl_srv_metrics.config(text=f"CPU: {srv_cpu:.1f}% │ RAM: {srv_mem:.1f} MB (PID: {self.engine.server_process.pid})")
        else:
            self.indicator_server.config(fg=self.c_red)
            self.btn_start_server.config(state="normal")
            self.btn_stop_server.config(state="disabled")
            self.lbl_srv_metrics.config(text="CPU: 0% │ RAM: 0.0 MB │ INACTIVO")

        # 4. Estado de Worker
        if self.engine.is_worker_running():
            self.indicator_worker.config(fg=self.c_green)
            self.btn_start_worker.config(state="disabled")
            self.btn_stop_worker.config(state="normal")
            wrk_cpu, wrk_mem = self.engine.get_proc_metrics(self.engine.worker_process)
            self.lbl_wrk_metrics.config(text=f"CPU: {wrk_cpu:.1f}% │ RAM: {wrk_mem:.1f} MB (PID: {self.engine.worker_process.pid})")
        else:
            self.indicator_worker.config(fg=self.c_red)
            self.btn_start_worker.config(state="normal")
            self.btn_stop_worker.config(state="disabled")
            self.lbl_wrk_metrics.config(text="CPU: 0% │ RAM: 0.0 MB │ INACTIVO")

        # 4.5 WATCHDOG (Auto-Heal con Cooldown)
        now_ts = time.time()
        if self.engine.expected_server_state and not self.engine.is_server_running():
            if now_ts - self.engine.last_server_restart > 8:
                self.engine.last_server_restart = now_ts
                self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [CRÍTICO] 🛡️ Watchdog: Servidor Web detectado como inactivo. Reiniciando...\n", "system")
                if self.auto_scroll_var.get():
                    self.txt_logs.see("end")
                self.engine.start_server(dev_mode=False)

        if self.engine.expected_worker_state and not self.engine.is_worker_running():
            if now_ts - self.engine.last_worker_restart > 8:
                self.engine.last_worker_restart = now_ts
                self.txt_logs.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] [CRÍTICO] 🛡️ Watchdog: Worker OSINT detectado como inactivo. Reiniciando...\n", "system")
                if self.auto_scroll_var.get():
                    self.txt_logs.see("end")
                self.engine.start_worker()

        # 5. Cargar logs
        self.read_live_logs()

        # Re-agendar bucle en 1000ms
        self.after_id = self.root.after(1000, self.update_loop)

    def start(self):
        # Manejar detención segura al cerrar ventana 'X'
        def on_close():
            if hasattr(self, 'after_id') and self.after_id:
                try:
                    self.root.after_cancel(self.after_id)
                except Exception:
                    pass
            self.engine.stop_all()
            try:
                self.root.destroy()
            except Exception:
                pass

        self.root.protocol("WM_DELETE_WINDOW", on_close)
        self.root.mainloop()


import multiprocessing

def launch_control_panel():
    engine = CobaltoEngine()
    use_cli = "--cli" in sys.argv or "--tui" in sys.argv or not HAS_GUI
    if not use_cli:
        try:
            gui = CobaltoGUI(engine)
            gui.start()
            return
        except Exception as display_err:
            print(f"[ADVERTENCIA] Fallo al iniciar entorno gráfico ({display_err}). Redireccionando a TUI...")
            use_cli = True

    if use_cli:
        try:
            import cobalto_launcher
            cobalto_launcher.main()
        except ImportError:
            print("[ERROR] No se pudo cargar el módulo cobalto_launcher.")
            sys.exit(1)


def main():
    multiprocessing.freeze_support()

    if "--control-panel" in sys.argv or "--gui" in sys.argv:
        launch_control_panel()
        return

    import cobalto_desktop
    cobalto_desktop.main()


if __name__ == "__main__":
    main()

