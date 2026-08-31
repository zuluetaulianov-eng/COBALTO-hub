@echo off
TITLE COBALTO - Subsistema Táctico de Video & CCTV Exportable
color 0A
cls
echo ==============================================================================
echo           📹 COBALTO HUB — SUBSISTEMA DE EXPORTACIÓN Y VIGILANCIA DE VIDEO
echo ==============================================================================
echo.
echo [1/3] Verificando entorno de Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no está instalado o no se encuentra en el PATH del sistema.
    echo Por favor instala Python 3.11+ e inténtalo de nuevo.
    pause
    exit /b 1
)

echo [2/3] Verificando dependencias instaladas...
python -c "import fastapi, aiohttp, PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo [AVISO] Instalando/actualizando paquetes necesarios en requirements.txt...
    python -m pip install -r requirements.txt
)

echo.
echo [3/3] Iniciando Servidor Autónomo de Video en http://localhost:8090 ...
echo Presiona Ctrl+C para detener el servidor.
echo.

python main.py --port 8090

pause
