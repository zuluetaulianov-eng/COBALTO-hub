"""
build_exe.py — Script de compilacion automatica para COBALTO HUB Executable (.exe)
Genera el ejecutable nativo de Windows 'dist/CobaltoHUB/CobaltoHUB.exe'.
Usa PyQt6 + QWebEngineView (mismo stack que CobaltoIA) para maxima robustez.
"""

import os
import subprocess
import sys

import tls_client

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

def build():
    print("==================================================")
    print(" [*] COMPILANDO COBALTO HUB EXECUTABLE (.EXE)")
    print(" [*] Engine: PyQt6 + QWebEngineView (CobaltoIA stack)")
    print("==================================================")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "static", "icons", "cobalto.ico")
    tls_client_dir = os.path.dirname(tls_client.__file__)

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "-y",
        "--noconsole",
        "--name=CobaltoHUB",
        f"--icon={icon_path}",
        "--add-data=templates;templates",
        "--add-data=static;static",
        f"--add-data={tls_client_dir};tls_client",
        "--exclude-module=PyQt6",
        "--hidden-import=pystray",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=engineio.async_drivers.asgi",
        "--hidden-import=psutil",
        "--hidden-import=cobalto_gui_launcher",
        "--hidden-import=cobalto_desktop",
        "--hidden-import=cobalto_worker",
        "--hidden-import=osint_ivss",
        "--hidden-import=osint_seniat",
        "cobalto_desktop.py"
    ]

    print(" [*] Ejecutando PyInstaller...")
    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        exe_path = os.path.join(base_dir, "dist", "CobaltoHUB", "CobaltoHUB.exe")
        print("\n==================================================")
        print(" [OK] COMPILACION COMPLETADA CON EXITO")
        print(f" [OK] Ejecutable listo en: {exe_path}")
        print("==================================================")
    else:
        print("\n[!] Error durante la compilacion con PyInstaller.")
        sys.exit(result.returncode)

if __name__ == '__main__':
    build()
