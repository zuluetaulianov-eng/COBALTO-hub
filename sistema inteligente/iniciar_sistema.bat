@echo off
chcp 65001 >nul
title Sistema Inteligente - Análisis de Texto
color 0A

echo =======================================================
echo    ⚡ SISTEMA INTELIGENTE - ANÁLISIS DE TEXTO ⚡
echo =======================================================
echo.

cd /d "%~dp0"

echo [1/3] Verificando e integrando interfaz web (frontend)...
python build_frontend.py

echo.
echo [2/3] Programando apertura inteligente del navegador...
start /b powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i=0; $i -lt 30; $i++) { Start-Sleep -Seconds 1; try { $r = Invoke-RestMethod -Uri 'http://localhost:8100/health' -ErrorAction Stop; if ($r.status -eq 'ok') { Start-Process 'http://localhost:8100'; break } } catch {} }"

echo.
echo [3/3] Iniciando servidor FastAPI en http://localhost:8100 ...
echo Presiona Ctrl+C para detener el servidor.
echo -------------------------------------------------------
python run.py

pause
