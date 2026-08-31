@echo off
title COBALTO HUB v16.0 - Instalador y Bootstrapper Automatizado
color 0B
setlocal enabledelayedexpansion
set OPENBLAS_NUM_THREADS=1
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set VECLIB_MAXIMUM_THREADS=1
set NUMEXPR_NUM_THREADS=1

cls
echo.
echo    ===================================================
echo             C O B A L T O   H U B   v 1 6 . 0
echo         Instalador de Entorno y Lanzador Dual
echo    ===================================================
echo.

:: --- 1. VERIFICAR INSTALACIÓN DE PYTHON ---
echo  [+] Verificando runtime de Python compatible...

set "PYTHON_CMD="

:: Comprobar si 'python' está disponible
where python >nul 2>nul
if !errorlevel! equ 0 (
    set "PYTHON_CMD=python"
) else (
    rem Comprobar si 'python3' está disponible
    where python3 >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=python3"
    )
)

:: Si no existe Python, proceder con la descarga e instalación silenciosa
if "%PYTHON_CMD%"=="" (
    echo  [ALERTA] Python no se encuentra instalado en el sistema.
    echo  [+] Iniciando descarga de Python 3.11.9 de forma automatizada...
    
    rem Descargar el instalador oficial silenciosamente usando curl - disponible en Win10 y 11
    curl -L -o python_installer.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    if !errorlevel! neq 0 (
        echo  [ERROR] No se pudo descargar Python automáticamente. Asegurese de tener conexion a internet o instale Python 3.10+ manualmente.
        pause
        exit /b 1
    )
    
    echo  [+] Instalando Python 3.11.9 silenciosamente - esto tardara aprox. 1 minuto...
    echo      * Por favor, apruebe los permisos de Administrador si Windows lo solicita.
    python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    
    if !errorlevel! neq 0 (
        echo  [ERROR] La instalacion automatica de Python ha fallado.
        del python_installer.exe >nul 2>nul
        pause
        exit /b 1
    )
    
    del python_installer.exe >nul 2>nul
    echo  [OK] Python 3.11.9 instalado correctamente en el sistema.
    
    rem Actualizar el PATH de la consola actual temporalmente
    set "PATH=%PATH%;C:\Program Files\Python311\;C:\Program Files\Python311\Scripts\"
    set "PYTHON_CMD=python"
)

:: --- 2. VERIFICAR COMPATIBILIDAD DE VERSION DE PYTHON ---
:: Comprobar que sea al menos Python 3.10
%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if !errorlevel! neq 0 (
    echo  [ALERTA] Se detecto una version obsoleta de Python. Requiere Python 3.10 o superior.
    echo  [+] Actualizando entorno a Python 3.11.9...
    
    curl -L -o python_installer.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del python_installer.exe >nul 2>nul
    
    set "PATH=%PATH%;C:\Program Files\Python311\;C:\Program Files\Python311\Scripts\"
    set "PYTHON_CMD=python"
)

echo  [OK] Entorno de Python verificado: compatible.
echo.

:: --- 3. VERIFICAR E INSTALAR DEPENDENCIAS DEL PROYECTO ---
echo  [+] Verificando dependencias y librerias del sistema...
%PYTHON_CMD% check_deps.py
if %errorlevel% neq 0 (
    echo  [ERROR] Verificacion o instalacion automatica de librerias fallida.
    pause
    exit /b 1
)
echo.

:: --- 4. INICIAR LANZADOR GRÁFICO (GUI OSINT) ---
echo  [+] Todo listo. Abriendo Sistema de Mando OSINT de COBALTO HUB (Local)...
%PYTHON_CMD% cobalto_gui_launcher.py %*

:: --- 5. LIMPIEZA AL CERRAR ---
echo.
echo  [!] El Lanzador de COBALTO HUB ha finalizado.
pause
