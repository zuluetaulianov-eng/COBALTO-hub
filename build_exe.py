"""
build_exe.py — Script de compilación automática para COBALTO HUB Executable (.exe)
Genera el ejecutable nativo de Windows 'dist/CobaltoHUB/CobaltoHUB.exe'.
"""

import os
import sys
import subprocess

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

def build():
    print("==================================================")
    print(" 🛠️ COMPILANDO COBALTO HUB EXECUTABLE (.EXE)")
    print("==================================================")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "static", "icons", "cobalto.ico")

    import tls_client
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
        "--hidden-import=webview",
        "--hidden-import=webview.platforms.winforms",
        "--hidden-import=webview.platforms.edgechromium",
        "--hidden-import=clr",
        "--hidden-import=cobalto_desktop",
        "--hidden-import=cobalto_worker",
        "cobalto_gui_launcher.py"
    ]

    print(f" [*] Ejecutando: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        exe_path = os.path.join(base_dir, "dist", "CobaltoHUB", "CobaltoHUB.exe")
        print("\n==================================================")
        print(" 🎉 COMPILACIÓN COMPLETADA CON ÉXITO")
        print(f" 📍 Ejecutable listo en: {exe_path}")
        print("==================================================")
    else:
        print("\n❌ Error durante la compilación con PyInstaller.")
        sys.exit(result.returncode)

if __name__ == '__main__':
    build()
