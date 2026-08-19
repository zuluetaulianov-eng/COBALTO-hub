@echo off
title COBALTO HUB — PyQt6 Desktop Launcher (Python Mode)
chcp 65001 > nul
echo ==================================================
echo  [*] Iniciando COBALTO HUB en Modo Python Desktop
echo  [*] Engine: PyQt6 + QWebEngineView + System Tray
echo ==================================================
echo.

python cobalto_desktop.py

if errorlevel 1 (
    echo.
    echo  [!] El proceso finalizo con errores.
)

pause
