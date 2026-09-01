"""
build_capacitor_apk.py — Compilador de APK Nativo Autónomo (Capacitor + ZROK) para Venezuela Noticias

Empaqueta la estructura HTML/CSS/JS completa en el directorio nativo 'www' de la APK,
permitiendo apertura offline instantánea (0ms) y consulta dinámica de noticias al túnel ZROK.
"""

import argparse
import os
import shutil
import subprocess
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WWW_DIR = os.path.join(BASE_DIR, "www")
STATIC_SRC = os.path.join(BASE_DIR, "static")
STATIC_DEST = os.path.join(WWW_DIR, "static")


def prepare_www_bundle(zrok_url: str):
    """Prepara la carpeta 'www' copiando assets estáticos e inyectando la URL de ZROK."""
    print(" [*] Preparando el paquete estático offline en 'www'...")
    os.makedirs(WWW_DIR, exist_ok=True)
    
    # Copiar estáticos si existen
    if os.path.exists(STATIC_SRC):
        if os.path.exists(STATIC_DEST):
            shutil.rmtree(STATIC_DEST)
        shutil.copytree(STATIC_SRC, STATIC_DEST)
        print("  • Assets estáticos (imágenes, CSS, JS) copiados a 'www/static/'")

    # Actualizar la URL por defecto en www/index.html
    index_path = os.path.join(WWW_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Reemplazar la constante DEFAULT_SERVER
        clean_url = zrok_url.rstrip("/")
        new_content = content.replace(
            'const DEFAULT_SERVER = "https://commandereliminatedextraction.share.zrok.io";',
            f'const DEFAULT_SERVER = "{clean_url}";'
        )
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  • URL Servidor ZROK configurada a: {clean_url}")

    print(" [+] Paquete Web 'www' listo para empaquetado nativo Capacitor.")


def check_prerequisites():
    """Verifica si Node.js / npx están instalados."""
    node_ok = shutil.which("node") is not None
    npx_ok = shutil.which("npx") is not None
    java_ok = shutil.which("java") is not None or "JAVA_HOME" in os.environ

    print(f"  • Node.js:  {'✅ Instalado' if node_ok else '❌ No instalado'}")
    print(f"  • NPX:      {'✅ Instalado' if npx_ok else '❌ No instalado'}")
    print(f"  • Java JDK: {'✅ Detectado' if java_ok else '⚠️ No detectado (requerido para gradle assemble)'}")
    return npx_ok


def build_capacitor_apk(zrok_url: str):
    """Ejecuta la secuencia de comandos de Capacitor para generar el APK nativo."""
    print("==================================================")
    print(" [*] INICIANDO CONSTRUCCIÓN APK CAPACITOR (OFFLINE)")
    print(f" [*] URL API ZROK: {zrok_url}")
    print("==================================================")

    prepare_www_bundle(zrok_url)

    if not check_prerequisites():
        print("\n[!] Node.js es necesario para compilar la APK automáticamente con Capacitor.")
        print("    Descarga e instala Node.js desde https://nodejs.org/")
        print("    Una vez instalado, ejecuta:")
        print("    npx @capacitor/cli add android")
        print("    npx @capacitor/cli copy")
        return False

    print("\n [*] Inicializando plataforma Android de Capacitor...")
    try:
        # 1. Asegurar instalación de dependencias Capacitor
        node_modules = os.path.join(BASE_DIR, "node_modules", "@capacitor", "android")
        if not os.path.exists(node_modules):
            print(" [*] Instalando dependencias nativas de Capacitor (@capacitor/core @capacitor/android)...")
            subprocess.run(["npm", "install", "@capacitor/core", "@capacitor/android", "@capacitor/cli", "--save-dev"], cwd=BASE_DIR, shell=True)

        # 2. Agregar plataforma android si no existe
        android_folder = os.path.join(BASE_DIR, "android")
        if not os.path.exists(android_folder):
            print(" [*] Ejecutando: npx @capacitor/cli add android")
            subprocess.run(["npx", "-y", "@capacitor/cli", "add", "android"], cwd=BASE_DIR, shell=True)

        # 3. Sincronizar bundle 'www' con el proyecto android
        print(" [*] Sincronizando bundle 'www' con Android...")
        subprocess.run(["npx", "-y", "@capacitor/cli", "sync", "android"], cwd=BASE_DIR, shell=True)

        # 4. Compilar APK con Gradle si gradlew existe
        gradlew = os.path.join(android_folder, "gradlew.bat" if sys.platform == "win32" else "gradlew")
        if os.path.exists(gradlew):
            print(" [*] Compilando APK nativo con Gradle...")
            cmd = [gradlew, "assembleDebug", "--no-daemon"]
            res = subprocess.run(cmd, cwd=android_folder, shell=True)
            if res.returncode == 0:
                print("\n==================================================")
                print(" [OK] ¡COMPILACIÓN DE APK COMPLETADA CON ÉXITO!")
                print(" [OK] El archivo APK se encuentra en:")
                print("      android/app/build/outputs/apk/debug/app-debug.apk")
                print("==================================================")
                return True

        print("\n[+] Proyecto Android generado exitosamente en la carpeta '/android'")
        print("    Para compilar el APK o abrir en Android Studio:")
        print("    npx @capacitor/cli open android")
        return True

    except Exception as e:
        print(f"[!] Error compilando Capacitor APK: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compilar APK Nativo Autónomo Capacitor para Venezuela Noticias")
    parser.add_argument("--url", default="https://commandereliminatedextraction.share.zrok.io", help="URL del túnel ZROK")
    args = parser.parse_args()

    build_capacitor_apk(args.url)
