@echo off
title Venezuela Noticias v1.0 — Servidor Autónomo
color 0B

cls
echo.
echo    ===================================================
echo        V E N E Z U E L A   N O T I C I A S   v 1 . 0
echo       Portal Autónomo - Sistema CMS Independiente
echo    ===================================================
echo.

:: --- 1. VERIFICAR RUNTIME DE PYTHON ---
echo  [+] Verificando runtime de Python...

set "PYTHON_CMD="

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto PYTHON_FOUND
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
    goto PYTHON_FOUND
)

python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python3"
    goto PYTHON_FOUND
)

:PYTHON_FOUND
if "%PYTHON_CMD%"=="" (
    echo.
    echo  [ERROR] Python no se encuentra instalado o no está en el PATH del sistema.
    echo  Por favor instala Python 3.10+ para continuar.
    echo.
    pause
    exit /b 1
)

echo  [OK] Python detectado: %PYTHON_CMD%
echo.

:: --- 2. VERIFICAR DEPENDENCIAS BÁSICAS ---
echo  [+] Verificando dependencias necesarias (fastapi, uvicorn, jinja2)...
%PYTHON_CMD% -c "import fastapi, uvicorn, jinja2" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [+] Instalando dependencias desde requirements.txt...
    %PYTHON_CMD% -m pip install -r requirements.txt --quiet
)

echo  [OK] Entorno verificado correctamente.
echo.

:: --- 3. MENÚ DE INICIO ---
:MENU
echo  Seleccione la opción de ejecución deseada:
echo.
echo   [1] Iniciar Portal Público de Noticias (Puerto 8085)
echo   [2] Iniciar Panel de Administración CMS (Puerto 8085)
echo   [3] Iniciar Servidor en Puerto Personalizado
echo   [0] Salir
echo.
set /p OPCION=" Ingrese su opción [1-3, 0]: "

if "%OPCION%"=="1" goto START_PUBLIC
if "%OPCION%"=="2" goto START_ADMIN
if "%OPCION%"=="3" goto START_CUSTOM
if "%OPCION%"=="0" goto END

echo.
echo  [!] Opción no válida. Intente de nuevo.
echo.
goto MENU

:START_PUBLIC
echo.
echo  [+] Levantando túnel público Zrok exclusivo para Venezuela Noticias...
where zrok >nul 2>nul
if %errorlevel% equ 0 (
    start /min cmd /c "zrok share reserved commandereliminatedextraction --override-endpoint http://localhost:8085 --force-local --headless > zrok.log 2>&1"
    echo  [OK] Túnel Zrok publicado en: https://commandereliminatedextraction.share.zrok.io
) else (
    echo  [ALERTA] Zrok no encontrado en PATH. El portal estará disponible solo en red local.
)
echo  [+] Iniciando Venezuela Noticias en modo Portal Público...
echo  [+] Abriendo navegador en http://localhost:8085/noticias ...
timeout /t 2 /nobreak >nul
start http://localhost:8085/noticias
%PYTHON_CMD% main.py --port 8085
taskkill /IM zrok.exe /F >nul 2>nul
goto END

:START_ADMIN
echo.
echo  [+] Levantando túnel público Zrok exclusivo para Venezuela Noticias...
where zrok >nul 2>nul
if %errorlevel% equ 0 (
    start /min cmd /c "zrok share reserved commandereliminatedextraction --override-endpoint http://localhost:8085 --force-local --headless > zrok.log 2>&1"
    echo  [OK] Túnel Zrok publicado en: https://commandereliminatedextraction.share.zrok.io
) else (
    echo  [ALERTA] Zrok no encontrado en PATH. El panel estará disponible solo en red local.
)
echo  [+] Iniciando Venezuela Noticias en modo CMS Administración...
echo  [+] Abriendo navegador en http://localhost:8085/vn-admin ...
timeout /t 2 /nobreak >nul
start http://localhost:8085/vn-admin
%PYTHON_CMD% main.py --port 8085
taskkill /IM zrok.exe /F >nul 2>nul
goto END

:START_CUSTOM
echo.
set /p PORT_USER=" Ingrese el puerto deseado (ej. 8090): "
if "%PORT_USER%"=="" set PORT_USER=8085
echo  [+] Iniciando Venezuela Noticias en el puerto %PORT_USER%...
echo  [+] Abriendo navegador en http://localhost:%PORT_USER%/noticias ...
timeout /t 2 /nobreak >nul
start http://localhost:%PORT_USER%/noticias
%PYTHON_CMD% main.py --port %PORT_USER%
goto END

:END
echo.
echo  [!] Servidor de Venezuela Noticias finalizado.
pause
