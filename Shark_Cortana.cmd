@echo off
title SHARK's Red Team Launcher - Powered by Zoey
mode con cols=110 lines=55
chcp 65001 >nul 2>&1
color 0B
cls
setlocal EnableDelayedExpansion

:: =============================================
:: 1. LLUVIA MATRIX CLÁSICA (azul intenso)
:: =============================================
for /l %%y in (1,1,55) do (
    cls
    color 0B
    for /l %%x in (1,1,%%y) do (
        set /a col=!random!%%110
        set /a char=!random!%%20
        if !char! lss 15 (
            <nul set /p =!char! 
        ) else (
            set "chars=█▓▒░01"
            <nul set /p =!chars:~!char! -15,1!
        )
        if !col! geq 109 echo.
    )
    ping -n 1 127.0.0.1 >nul >nul
)
cls

:: =============================================
:: 2. BARRA DE CARGA - AZUL TALIBÁN
:: =============================================
cls
color 0B
echo.
echo.
echo                              ╔═══════════════════════════════╗
echo                              ║         T  A  L  I  B  A  N    ║
echo                              ╚═══════════════════════════════╝
echo.
for /l %%i in (1,1,20) do (
    set /a p=%%i*5
    set "bar=████████████████████"
    set "empty=────────────────────"
    cls
    color 0B
    echo.
    echo                              ╔═══════════════════════════════╗
    echo                              ║         T  A  L  I  B  A  N    ║
    echo                              ╚═══════════════════════════════╝
    echo.
    echo                                 [!bar:~0,%%i!!empty:~%%i!]  !p!%%
    echo.
    <nul set /p "=                            BREACH PROTOCOL ACTIVE"
    ping -n 1 127.0.0.1 >nul >nul
)
timeout /t 1 >nul >nul
cls

:: =============================================
:: 3. MENÚ PRINCIPAL - TALIBAN EN AZUL PURO
:: =============================================
:LOGO
cls
color 0B
echo.
echo                       ████████╗ █████╗ ██╗     ██╗██████╗  █████╗ ███╗   ██╗
echo                       ╚══██╔══╝██╔══██╗██║     ██║██╔══██╗██╔══██╗████╗  ██║
echo                          ██║   ███████║██║     ██║██████╔╝███████║██╔██╗ ██║
echo                          ██║   ██╔══██║██║     ██║██╔══██╗██╔══██║██║╚██╗██║
echo                          ██║   ██║  ██║███████╗██║██████╔╝██║  ██║██║ ╚████║
echo                          ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝
echo.
color 1F
echo.
echo                        ╔══════════════════════════════════════════════════╗
echo                        ║                   R E D   T E A M                ║
echo                        ║                                                  ║
echo                        ║                CYBER SEGURIDAD                   ║
echo                        ║                                                  ║
echo                        ╚══════════════════════════════════════════════════╝
echo.
color 0B
echo.
echo                                   ┌────────────────────────────┐
echo                                   │  [1] Ejecutar payload      │
echo                                   │  [2] Iniciar servidor      │
echo                                   │  [3] Cerrar sesión         │
echo                                   └────────────────────────────┘
echo.
color 0F
set /p choice=                               > Selecciona operación [1-3]: 

if "%choice%"=="1" goto LIST_PY
if "%choice%"=="2" goto SERVER_PY
if "%choice%"=="3" goto END

color 0C
echo.
echo                                   ┌[!] ACCESO DENEGADO [!]┐
timeout /t 2 >nul
goto LOGO

:: =============================================
:: LISTADO DE PAYLOADS (azul coherente)
:: =============================================
:LIST_PY
cls
color 0B
echo.
echo                        ╔══════════════════════════════════════════════════╗
echo                        ║               PAYLOADS DISPONIBLES               ║
echo                        ╚══════════════════════════════════════════════════╝
echo.
set count=0
for %%f in (*.py) do (
    set /a count+=1
    set "script[!count!]=%%f"
    echo                                   [!count!] %%f
)
if %count%==0 (
    color 0C
    echo.
    echo                               No se detectaron payloads activos
    echo                               Inserta los archivos .py en este directorio
    echo.
    pause
    goto LOGO
)
echo.
echo                                   [0] Volver
echo.
color 0F
set /p num=                               > Selecciona payload [0 para volver]: 

if "%num%"=="0" goto LOGO
if defined script[%num%] (
    cls
    color 09
    echo.
    echo                        ╔══════════════════════════════════════════════════╗
    echo                        ║               EJECUTANDO OPERACIÓN               ║
    echo                        ╚══════════════════════════════════════════════════╝
    echo.
    echo                                   Payload: !script[%num%]!
    timeout /t 2 >nul
    python "!script[%num%]!"
    echo.
    pause
    goto LOGO
) else (
    color 0C
    echo                               Payload no válido
    timeout /t 2 >nul
    goto LIST_PY
)

:: =============================================
:: SERVIDOR HTTP (azul)
:: =============================================
:SERVER_PY
cls
color 0B
echo.
echo                        ╔══════════════════════════════════════════════════╗
echo                        ║               SERVIDOR HTTP INICIADO             ║
echo                        ╚══════════════════════════════════════════════════╝
echo.
set /p port=                               > Puerto [Enter = 8000]: 
if "%port%"=="" set port=8000
echo.
echo                                   Servidor activo en:
echo                                   http://localhost:%port%
echo.
echo                                   Ctrl+C para detener
echo.
python -m http.server %port%
pause
goto LOGO

:: =============================================
:: SALIDA
:: =============================================
:END
cls
color 0B
echo.
echo.
echo                                Operación finalizada.
echo                                Conexión segura cerrada.
echo.
echo                                     TALIBAN OUT.
echo.
timeout /t 4 >nul
exit