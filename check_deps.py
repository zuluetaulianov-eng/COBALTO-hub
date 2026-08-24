"""check_deps.py - Verificador de dependencias del proyecto"""

import importlib
import subprocess
import sys
import time

REQUIRED = {
    "requests": "requests",
    "feedparser": "feedparser",
    "bs4": "beautifulsoup4",
    "lxml_html_clean": "lxml-html-clean",
    "aiohttp": "aiohttp",
    "urllib3": "urllib3",
    "fastapi": "fastapi",
    "pydantic": "pydantic",
    "groq": "groq",
    "openai": "openai",
    "jinja2": "jinja2",
    "dotenv": "python-dotenv",
    "networkx": "networkx",
    "community": "python-louvain",
    "playwright": "playwright",
    "telegram": "python-telegram-bot",
    "PIL": "pillow",
    "dateutil": "python-dateutil",
    "uvicorn": "uvicorn",
    "bleach": "bleach[css]",
    "prometheus_client": "prometheus-client",
    "psutil": "psutil",
    "tls_client": "tls-client",
    "pystray": "pystray",
}


def check(mod):
    try:
        importlib.import_module(mod)
        return True
    except ImportError:
        return False


def install(pkg):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    print("=" * 55)
    print("  COBALTO HUB - Verificacion de Dependencias")
    print("=" * 55)
    missing = []
    for mod, pkg in REQUIRED.items():
        if check(mod):
            print(f"  [OK] {pkg}")
        else:
            missing.append((mod, pkg))
            print(f"  [..] {pkg}")

    if missing:
        print(f"\n  Instalando {len(missing)} paquete(s)...")
        for mod, pkg in missing:
            print(f"    -> {pkg}...", end=" ", flush=True)
            if install(pkg):
                print("OK")
                time.sleep(0.3)
            else:
                print("ERROR")
                sys.exit(1)

    # Auto-instalar navegadores de Playwright
    print("\n  [+] Verificando navegadores de Playwright (Chromium)...")
    try:
        # Ejecutar silenciosamente la descarga de Chromium
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("  [OK] Playwright Chromium listo.")
    except Exception as e:
        print(f"  [ADVERTENCIA] No se pudo instalar Playwright Chromium: {e}")

    print("\n  [OK] Todas las dependencias estan listas")
    print("=" * 55)


if __name__ == "__main__":
    main()
