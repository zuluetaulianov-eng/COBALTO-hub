@echo off
title COBALTO HUB — Standalone EXE Launcher
chcp 65001 > nul
echo ==================================================
echo  [*] Lanzando COBALTO HUB Executable (.EXE)
echo  [*] Engine: PyQt6 + QWebEngineView + System Tray
echo ==================================================
echo.

REM Detener instancias previas si existen
echo  [*] Verificando procesos previos...
taskkill /F /IM CobaltoHUB.exe >nul 2>&1

echo  [*] Iniciando CobaltoHUB.exe desde dist...
echo.

if exist "dist\CobaltoHUB\CobaltoHUB.exe" (
    "dist\CobaltoHUB\CobaltoHUB.exe"
) else (
    echo  [!] No se encontro dist\CobaltoHUB\CobaltoHUB.exe.
    echo  [!] Por favor compila primero ejecutando: python build_exe.py
)

echo.
echo  [*] Proceso finalizado.
pause
