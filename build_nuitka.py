"""
build_nuitka.py — Script de compilación nativa a C/C++ usando Nuitka Compiler
Genera un ejecutable binario nativo optimizado 'dist_nuitka/cobalto_desktop.dist/cobalto_desktop.exe'.
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
    print(" [*] COMPILANDO COBALTO HUB CON NUITKA COMPILER")
    print(" [*] Traducción directa de Python -> C/C++ -> Machine Code")
    print("==================================================")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "static", "icons", "cobalto.ico")
    tls_client_dir = os.path.dirname(tls_client.__file__)

    cmd = [
        sys.executable,
        "-m", "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={icon_path}",
        "--include-data-dir=templates=templates",
        "--include-data-dir=static=static",
        f"--include-data-dir={tls_client_dir}=tls_client",
        "--low-memory",
        "--jobs=2",
        "--lto=no",
        "--nofollow-import-to=PyQt6",
        "--nofollow-import-to=scipy",
        "--nofollow-import-to=numpy",
        "--nofollow-import-to=pandas",
        "--nofollow-import-to=sklearn",
        "--nofollow-import-to=matplotlib",
        "--output-dir=dist_nuitka",
        "cobalto_desktop.py"
    ]

    print(" [*] Ejecutando Nuitka Compiler (C/C++ Build Process)...")
    print(" [*] Comando:", " ".join(cmd))

    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        dist_dir = os.path.join(base_dir, "dist_nuitka", "cobalto_desktop.dist")
        exe_path = os.path.join(dist_dir, "cobalto_desktop.exe")
        print("\n==================================================")
        print(" [OK] COMPILACIÓN C/C++ COMPLETADA CON ÉXITO")
        print(f" [OK] Binario nativo generado en: {exe_path}")
        print("==================================================")
    else:
        print("\n[!] Error durante la compilación con Nuitka.")
        sys.exit(result.returncode)

if __name__ == '__main__':
    build()
