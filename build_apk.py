"""
build_apk.py — Script de automatización para empaquetar Venezuela Noticias y COBALTO HUB en un archivo APK Nativo de Android (.apk)

Soporta dos métodos de compilación:
1. TWA (Trusted Web Activity via Bubblewrap / Google Official) -> APK nativo ultraligero (~2MB) con Service Worker PWA.
2. Capacitor Android (Native Webview Bundle) -> APK 100% offline empaquetado.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TWA_MANIFEST_PATH = os.path.join(BASE_DIR, "twa-manifest.json")


def generate_twa_manifest(app_url: str, app_name: str = "Venezuela Noticias", package_id: str = "com.venezuelanoticias.app"):
    """
    Genera el archivo de configuración twa-manifest.json necesario para Bubblewrap / TWA.
    """
    manifest_data = {
        "packageId": package_id,
        "host": app_url.replace("https://", "").replace("http://", "").split("/")[0],
        "name": app_name,
        "launcherName": "VenezuelaNoticias",
        "display": "standalone",
        "themeColor": "#00E5FF",
        "navigationColor": "#07090e",
        "backgroundColor": "#07090e",
        "enableNotifications": True,
        "startUrl": "/noticias",
        "iconUrl": f"{app_url.rstrip('/')}/static/img/vn_logo.png",
        "maskableIconUrl": f"{app_url.rstrip('/')}/static/img/vn_logo.png",
        "splashScreenFadeOutDuration": 300,
        "signingKey": {
            "path": "./android-keystore.ks",
            "alias": "android"
        },
        "appVersionName": "1.0.0",
        "appVersionCode": 1,
        "shortcuts": [],
        "generatorApp": "COBALTO-HUB-APK-Builder"
    }

    with open(TWA_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print(f" [+] Configuración TWA generada en: {TWA_MANIFEST_PATH}")
    return TWA_MANIFEST_PATH


def check_prerequisites():
    """Verifica si Node.js / npx / java están disponibles en el sistema."""
    print(" [*] Verificando herramientas de compilación Android...")
    node_ok = shutil.which("node") is not None
    npx_ok = shutil.which("npx") is not None
    java_ok = shutil.which("java") is not None or "JAVA_HOME" in os.environ

    print(f"  • Node.js: {'✅ Instalado' if node_ok else '❌ No encontrado'}")
    print(f"  • NPX:     {'✅ Instalado' if npx_ok else '❌ No encontrado'}")
    print(f"  • Java JDK: {'✅ Detectado' if java_ok else '⚠️ No detectado en PATH (requerido para APK firmado)'}")

    return npx_ok


def build_twa_apk(app_url: str):
    """Ejecuta la compilación Bubblewrap TWA mediante npx."""
    print("==================================================")
    print(" [*] COMPILANDO APK NATIVO DE ANDROID (TWA)")
    print(f" [*] URL Objetivo: {app_url}")
    print("==================================================")

    generate_twa_manifest(app_url)

    if not check_prerequisites():
        print("\n[!] Node.js y NPX son requeridos para compilar el APK automáticamente.")
        print("    Descargue e instale Node.js desde https://nodejs.org/")
        print("    O bien use el siguiente comando manual tras instalar Node.js:")
        print(f"    npx @bubblewrap/cli init --manifest={app_url.rstrip('/')}/manifest.json")
        print("    npx @bubblewrap/cli build")
        return False

    print("\n [*] Iniciando generación de proyecto Android Bubblewrap...")
    try:
        cmd = ["npx", "-y", "@bubblewrap/cli", "build"]
        print(f" [*] Ejecutando: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=BASE_DIR, shell=True)
        if res.returncode == 0:
            print("\n==================================================")
            print(" [OK] COMPILACIÓN DE APK COMPLETADA CON ÉXITO")
            print(" [OK] El archivo .apk firmado se encuentra en la carpeta del proyecto.")
            print("==================================================")
            return True
    except Exception as e:
        print(f"[!] Error ejecutando Bubblewrap: {e}")

    print("\n[i] Para construir el APK de forma interactiva en la terminal, ejecute:")
    print("    npx @bubblewrap/cli init --manifest=http://localhost:8085/manifest.json")
    print("    npx @bubblewrap/cli build")
    return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Compilar APK Nativo de Android para Venezuela Noticias / COBALTO")
    parser.add_argument("--url", default="http://localhost:8085", help="URL del servidor web hospedado")
    args = parser.parse_args()

    build_twa_apk(args.url)
