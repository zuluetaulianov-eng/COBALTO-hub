"""
COBALTO HUB — Generador de Instalador y Paquete de Distribución (.EXE / .ZIP / .ISS)
Genera el paquete oficial de instalación listo para llevar e instalar en cualquier PC con Windows.
"""

import os
import sys
import zipfile
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist", "CobaltoHUB")
OUTPUT_DIR = os.path.join(BASE_DIR, "dist_installer")

def create_inno_setup_script():
    """Genera el script .iss oficial para Inno Setup Compiler."""
    out_dir_clean = OUTPUT_DIR.replace('\\', '\\\\')
    icon_path_clean = os.path.join(BASE_DIR, 'static', 'icons', 'cobalto.ico').replace('\\', '\\\\')
    dist_dir_clean = DIST_DIR.replace('\\', '\\\\')
    
    iss_content = f"""; Script de Instalación Inno Setup para COBALTO HUB C4I
#define MyAppName "COBALTO HUB"
#define MyAppVersion "12.1"
#define MyAppPublisher "COBALTO Intelligence Team"
#define MyAppExeName "CobaltoHUB.exe"

[Setup]
AppId={{{{C0BA170-C41-489A-901B-COBALTO121}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
OutputDir={out_dir_clean}
OutputBaseFilename=Setup_CobaltoHUB_v12.1
SetupIconFile={icon_path_clean}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: unchecked

[Files]
Source: "{dist_dir_clean}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "{{cm:LaunchProgram,{{StringChange(MyAppName, '&', '&&')}}}}"; Flags: nowait postinstall skipifsilent
"""
    iss_path = os.path.join(BASE_DIR, "CobaltoHUB_Installer.iss")
    with open(iss_path, "w", encoding="utf-8") as f:
        f.write(iss_content)
    print(f" [OK] Script de Inno Setup creado en: {iss_path}")

def build_zip_package():
    """Crea un paquete ZIP autocomprimido portable listo para extraer en cualquier PC."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    zip_path = os.path.join(OUTPUT_DIR, "CobaltoHUB_v12.1_Portable.zip")
    
    print(f" [*] Comprimiendo paquete ejecutable en: {zip_path} ...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(DIST_DIR):
            for file in files:
                abs_file = os.path.join(root, file)
                rel_file = os.path.relpath(abs_file, DIST_DIR)
                zipf.write(abs_file, os.path.join("CobaltoHUB", rel_file))
                
    print(f" [OK] Paquete Portable listo: {zip_path} ({os.path.getsize(zip_path) / (1024*1024):.1f} MB)")

def create_windows_auto_installer_bat():
    """Crea un script autoinstalador para Windows que desempaqueta e instala con 1-clic."""
    bat_content = """@echo off
title Instalador Tactico — COBALTO HUB C4I v12.1
color 0A
cls
echo ============================================================
echo   COBALTO HUB v12.1 — INSTALADOR AUTÓNOMO TÁCTICO C4I
echo ============================================================
echo.
echo  Instalando COBALTO HUB en el equipo objetivo...
echo.

set "TARGET_DIR=%LOCALAPPDATA%\\CobaltoHUB"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

echo  [*] Copiando archivos del sistema...
xcopy /E /I /Y /Q "%~dp0CobaltoHUB\\*" "%TARGET_DIR%\\" >nul

echo  [*] Creando acceso directo en el Escritorio...
set "SHORTCUT_PATH=%USERPROFILE%\\Desktop\\COBALTO HUB C4I.lnk"
set "TARGET_EXE=%TARGET_DIR%\\CobaltoHUB.exe"

powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT_PATH%');$s.TargetPath='%TARGET_EXE%';$s.WorkingDirectory='%TARGET_DIR%';$s.IconLocation='%TARGET_EXE%,0';$s.Save()"

echo.
echo ============================================================
echo   ¡INSTALACIÓN COMPLETADA CON ÉXITO!
echo   Acceso directo creado en el Escritorio: COBALTO HUB C4I
echo ============================================================
echo.
pause
"""
    bat_path = os.path.join(OUTPUT_DIR, "Instalar_CobaltoHUB.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    print(f" [OK] Lanzador de instalación automática creado en: {bat_path}")

if __name__ == "__main__":
    if not os.path.exists(DIST_DIR):
        print(f"[!] ERROR: No existe la carpeta {DIST_DIR}. Ejecuta build_exe.py primero.")
        sys.exit(1)
        
    print("==================================================")
    print(" [*] GENERANDO PAQUETES DE INSTALACION — COBALTO HUB")
    print("==================================================")
    create_inno_setup_script()
    build_zip_package()
    create_windows_auto_installer_bat()
    print("==================================================")
    print(f" [OK] PROCESO COMPLETADO. Archivos guardados en:\n --> {OUTPUT_DIR}")
    print("==================================================")
