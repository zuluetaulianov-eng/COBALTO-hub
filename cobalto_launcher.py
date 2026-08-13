#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cobalto_launcher.py — Lanzador táctico interactivo y monitor de sistema
========================================================================
Proporciona un menú de inicio visual para seleccionar los modos de ejecución
y entra en un Panel de Control en tiempo real (TUI) con métricas del sistema,
estado de los procesos del Servidor/Worker y visor de logs unificado.

Soporta Windows, macOS y Linux de forma nativa sin dependencias complejas.
"""

import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("cobalto.launcher")

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

# Códigos ANSI para colores tácticos (cyberpunk)
CLEAR_SCREEN = "\033[2J\033[H"
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[1;31m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[1;36m"
WHITE = "\033[1;37m"
DIM = "\033[2m"

# Rutas de los logs
WORKER_LOG = BASE_DIR / "worker.log"
SERVER_LOG = BASE_DIR / "server.log"

class KeyReader:
    """Lector de teclado no-bloqueante cross-platform."""
    def __init__(self):
        self.is_windows = os.name == 'nt'
        if not self.is_windows:
            try:
                import termios
                import tty
                self.tty = tty
                self.termios = termios
                self.old_settings = termios.tcgetattr(sys.stdin)
                self.has_termios = True
            except ImportError:
                self.has_termios = False

    def get_key(self):
        if self.is_windows:
            import msvcrt
            if msvcrt.kbhit():
                try:
                    return msvcrt.getch().decode('utf-8', errors='ignore').lower()
                except Exception:
                    return None
            return None
        else:
            if not getattr(self, 'has_termios', False):
                return None
            import select
            self.tty.setcbreak(sys.stdin.fileno())
            try:
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    return sys.stdin.read(1).lower()
            except Exception:
                pass
            finally:
                self.termios.tcsetattr(sys.stdin, self.termios.TCSADRAIN, self.old_settings)
            return None


class CobaltoLauncher:
    def __init__(self):
        self.server_process = None
        self.worker_process = None
        self.selected_mode = None
        self.key_reader = KeyReader()
        self.running = True
        self.start_time = time.time()

    def print_header(self):
        print(f"{CYAN}{BOLD}")
        print("  ╔═══════════════════════════════════════════════════════════════╗")
        print("  ║               C O B A L T O   H U B   v 9 . 0                 ║")
        print("  ║               - TACTICAL LAUNCHER & MONITOR -                 ║")
        print("  ╚═══════════════════════════════════════════════════════════════╝")
        print(f"{RESET}")

    def show_menu(self):
        print(CLEAR_SCREEN)
        self.print_header()
        print(f"  {WHITE}Seleccione el modo de operación táctico:{RESET}\n")
        print(f"  {CYAN}[1]{RESET} {BOLD}Modo Completo (Recomendado){RESET}")
        print("      Inicia el Servidor Web (puerto 8083) + el Extractor OSINT.")
        print("      Ideal para producción. Todo automatizado.")
        print("")
        print(f"  {CYAN}[2]{RESET} {BOLD}Modo Desarrollo (--dev){RESET}")
        print("      Servidor Web con autorecarga activa + el Extractor OSINT.")
        print("      Ideal para pruebas locales y depuración.")
        print("")
        print(f"  {CYAN}[3]{RESET} {BOLD}Solo Servidor Web (--no-worker){RESET}")
        print("      Inicia únicamente el servidor. Requiere caché persistente.")
        print("      Bajo consumo de recursos.")
        print("")
        print(f"  {CYAN}[4]{RESET} {BOLD}Solo Extractor OSINT (--only-worker){RESET}")
        print("      Ejecuta los ciclos de extracción en loop sin levantar la web.")
        print("      Ideal para servidores dedicados de base de datos.")
        print("")
        print(f"  {RED}[5] Salir del Lanzador{RESET}")
        print("")
        print(f"  {DIM}Ingrese opción [1-5]: {RESET}", end="", flush=True)

        # Bucle de selección
        while True:
            key = self.key_reader.get_key()
            if not key:
                time.sleep(0.05)
                continue
            if key == '1':
                return "normal"
            elif key == '2':
                return "dev"
            elif key == '3':
                return "no-worker"
            elif key == '4':
                return "only-worker"
            elif key == '5' or key == 'q':
                sys.exit(0)

    def start_processes(self, mode):
        self.selected_mode = mode
        self.start_time = time.time()

        # Eliminar logs previos para arrancar limpio si es necesario
        for log in (WORKER_LOG, SERVER_LOG):
            if log.exists():
                try:
                    log.unlink()
                except Exception:
                    pass

        # ── Levantar Worker ──
        if mode in ("normal", "dev", "only-worker"):
            args = [sys.executable, "cobalto_worker.py"]
            # Abrir archivo de log para escritura
            log_file = open(str(WORKER_LOG), "w", encoding="utf-8")
            self.worker_process = subprocess.Popen(
                args,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR)
            )

        # ── Levantar Servidor ──
        if mode in ("normal", "dev", "no-worker"):
            args = [sys.executable, "app.py"]
            if mode == "dev":
                args.append("--dev")
            log_file = open(str(SERVER_LOG), "w", encoding="utf-8")
            self.server_process = subprocess.Popen(
                args,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR)
            )

    def stop_processes(self):
        """Detiene de forma segura todos los procesos activos."""
        for name, proc in (("Servidor Web", self.server_process), ("Extractor OSINT", self.worker_process)):
            if proc and proc.poll() is None:
                try:
                    # En Windows, a veces Popen.terminate() no es suficiente para árboles de procesos
                    if os.name == 'nt':
                        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        proc.terminate()
                        proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

    def draw_progress_bar(self, percentage, width=20):
        """Genera una barra de progreso cyberpunk estilo bloque."""
        filled = int(width * percentage / 100)
        bar = "█" * filled + "░" * (width - filled)
        return bar

    def get_system_metrics(self):
        """Obtiene métricas de sistema general."""
        if not HAS_PSUTIL:
            return "N/A", "N/A", "N/A", "N/A"
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            cpu_bar = self.draw_progress_bar(cpu)
            ram_bar = self.draw_progress_bar(ram)
            return f"{cpu_bar} {cpu}%", f"{ram_bar} {ram}%", cpu, ram
        except Exception:
            return "ERROR", "ERROR", 0, 0

    def get_process_stats(self, proc):
        """Retorna detalles del consumo de un proceso usando psutil."""
        if not proc or proc.poll() is not None:
            return f"{RED}DETENIDO{RESET}", "N/A", "N/A"

        if not HAS_PSUTIL:
            return f"{GREEN}CORRIENDO{RESET}", "N/A", "N/A"

        try:
            p = psutil.Process(proc.pid)
            # psutil.Process puede lanzar excepciones si el proceso muere entre llamadas
            cpu = p.cpu_percent(interval=0.1)
            mem = p.memory_info().rss / (1024 * 1024) # a MB
            return f"{GREEN}ACTIVO{RESET}", f"{cpu:.1f}%", f"{mem:.1f} MB"
        except Exception:
            return f"{YELLOW}INICIANDO{RESET}", "N/A", "N/A"

    def tail_logs(self, lines_count=6):
        """Toma las últimas líneas combinadas de los logs para mostrar en pantalla."""
        lines = []
        # Leemos el worker.log
        if WORKER_LOG.exists():
            try:
                with open(WORKER_LOG, "r", encoding="utf-8", errors="ignore") as f:
                    worker_lines = f.readlines()[-lines_count:]
                    lines.extend([f"{GREEN}[WORKER]{RESET} {line.strip()}" for line in worker_lines])
            except Exception:
                pass

        # Leemos el server.log
        if SERVER_LOG.exists():
            try:
                with open(SERVER_LOG, "r", encoding="utf-8", errors="ignore") as f:
                    server_lines = f.readlines()[-lines_count:]
                    lines.extend([f"{CYAN}[SERVER]{RESET} {line.strip()}" for line in server_lines])
            except Exception:
                pass

        # Retornar las más recientes ordenadas
        return lines[-lines_count:]

    def show_monitor_dashboard(self):
        """Bucle de renderizado del panel de control táctico."""
        print(CLEAR_SCREEN)

        while self.running:
            # Obtener datos
            cpu_str, ram_str, cpu_val, ram_val = self.get_system_metrics()

            srv_status, srv_cpu, srv_mem = self.get_process_stats(self.server_process)
            wrk_status, wrk_cpu, wrk_mem = self.get_process_stats(self.worker_process)

            uptime = str(datetime.now() - datetime.fromtimestamp(self.start_time)).split('.')[0]

            # Limpiar terminal y re-dibujar de forma compacta
            print("\033[H", end="") # Cursor al inicio

            print(f"{CYAN}{BOLD}")
            print("  ╔═══════════════════════════════════════════════════════════════╗")
            print("  ║          PANEL TACTICO DE CONTROL COBALTO - OPERATIVO         ║")
            print("  ╚═══════════════════════════════════════════════════════════════╝")
            print(f"{RESET}")

            # Sección de recursos
            print(f"  {BOLD}[ MONITOREO DEL SISTEMA ]{RESET}═════════════════════════════════════════")
            print(f"   CPU General:  {CYAN}{cpu_str:<30}{RESET} Uptime: {YELLOW}{uptime}{RESET}")
            print(f"   RAM General:  {CYAN}{ram_str:<30}{RESET} Puerto Web: {YELLOW}8083{RESET}")
            print("")

            # Sección de Procesos
            print(f"  {BOLD}[ ESTADO DE LOS PROCESOS ]{RESET}════════════════════════════════════════")
            print("   PROCESO         ESTADO       PID       CPU       MEMORIA")
            print("   ─────────────── ──────────── ───────── ───────── ─────────────")

            srv_pid = self.server_process.pid if self.server_process else "N/A"
            print(f"   Servidor Web    {srv_status:<21} {srv_pid:<9} {srv_cpu:<9} {srv_mem}")

            wrk_pid = self.worker_process.pid if self.worker_process else "N/A"
            print(f"   Extractor OSINT {wrk_status:<21} {wrk_pid:<9} {wrk_cpu:<9} {wrk_mem}")
            print("")

            # Visor de logs en vivo
            print(f"  {BOLD}[ FEED DE ACTIVIDAD EN TIEMPO REAL ]{RESET}══════════════════════════════")
            logs = self.tail_logs(6)
            if logs:
                for log in logs:
                    # Limitar ancho de línea a 75 chars para evitar deformar caja
                    print(f"   {log[:72]}")
            else:
                print(f"   {DIM}Esperando inicialización de logs del sistema...{RESET}")
                print("")
                print("")
                print("")
                print("")
                print("")
            print("  ════════════════════════════════════════════════════════════════")
            print(f"  {BOLD}Controles:{RESET} {CYAN}[R] Reiniciar Procesos{RESET}  │  {YELLOW}[K] Detener{RESET}  │  {RED}[Q] Salir{RESET}")
            print(f"  {DIM}Presione una tecla para actuar...{RESET}", end="", flush=True)

            # Escuchar input no bloqueante
            for _ in range(20): # subdividir los 2 segundos de actualización para responder rápido al teclado
                key = self.key_reader.get_key()
                if key:
                    if key == 'q':
                        self.stop_processes()
                        self.running = False
                        sys.exit(0)
                    elif key == 'k':
                        self.stop_processes()
                        logger.info("Procesos detenidos por el operador.")
                    elif key == 'r':
                        self.stop_processes()
                        logger.info("Reiniciando procesos...")
                        time.sleep(1)
                        self.start_processes(self.selected_mode)
                        break # salir del sleep e ir a redibujar inmediatamente
                time.sleep(0.1)

def main():
    global HAS_PSUTIL
    # Instalar psutil automáticamente si check_deps.py no se ha corrido
    if not HAS_PSUTIL:
        print("[LAUNCHER] psutil no instalado. Intentando auto-instalación para monitor en vivo...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "--quiet"])
            HAS_PSUTIL = True
            print("[LAUNCHER] psutil instalado con éxito.")
        except Exception:
            print("[LAUNCHER] No se pudo instalar psutil automáticamente. Continuará sin soporte de monitor extendido.")

    launcher = CobaltoLauncher()

    # Procesar argumentos si se pasaron por consola (ej. start_cobalto.bat --dev)
    mode = None
    if "--only-worker" in sys.argv:
        mode = "only-worker"
    elif "--no-worker" in sys.argv:
        mode = "no-worker"
    elif "--dev" in sys.argv:
        mode = "dev"
    elif "--normal" in sys.argv or "-n" in sys.argv:
        mode = "normal"

    # Si no se pasó argumento, mostrar el menú interactivo
    if not mode:
        mode = launcher.show_menu()

    try:
        launcher.start_processes(mode)
        launcher.show_monitor_dashboard()
    except KeyboardInterrupt:
        pass
    finally:
        launcher.stop_processes()
        print(f"\n{YELLOW}[SYSTEM] Todos los servicios detenidos de manera segura. Exiting.{RESET}")

if __name__ == "__main__":
    main()
