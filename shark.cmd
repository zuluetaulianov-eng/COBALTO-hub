@echo off
title SHARK's Red Team Launcher - Powered by Zoey
mode con cols=100 lines=50
color 0A
cls
setlocal EnableDelayedExpansion

:: =============================================
:: 1. LLUVIA MATRIX (3 segundos, brutal)
:: =============================================
for /l %%n in (1,1,80) do (
    set "line="
    for /l %%i in (1,1,100) do (
        set /a r=!random!%%12
        if !r! lss 9 set "line=!line! "
        if !r! equ 9 set "line=!line!0"
        if !r! equ 10 set "line=!line!1"
        if !r! equ 11 set "line=!line!Û"
    )
    <nul set /p =!line!
    echo.
    ping -n 1 127.0.0.1 >nul >nul
)
cls

:: =============================================
:: 2. BARRA DE CARGA PICA
:: =============================================
echo.
echo                         ษอออออออออออออออออออออออออออออออออออออออป
echo                         บ       INICIANDO SISTEMA RED TEAM      บ
echo                         ศอออออออออออออออออออออออออออออออออออออออผ
echo.
echo                                   [          ]
echo.
set "bar=          "
set "load=HACKING SYSTEM"
<nul set /p "=                                   !load!"
for /l %%i in (1,1,20) do (
    set "bar=#%bar:~1%"
    <nul set /p "=.">CON
    ping -n 1 127.0.0.1 >nul >nul
    cls
    echo.
    echo                         ษอออออออออออออออออออออออออออออออออออออออป
    echo                         บ       INICIANDO SISTEMA RED TEAM      บ
    echo                         ศอออออออออออออออออออออออออออออออออออออออผ
    echo.
    echo                                   [!bar!]
    echo.
    <nul set /p "=                                   !load!"
)
cls

:: =============================================
:: 3. LOGO FINAL CON COLORES QUE RESPIRAN
:: =============================================
:LOGO
color 0A
cls
echo.
echo                        ÛÛÛÛÛÛÛปÛÛป ÛÛป ÛÛÛÛÛป ÛÛÛÛÛÛป ÛÛป ÛÛป
echo                        ÛÛษออออผÛÛบ ÛÛบÛÛษออÛÛปÛÛษออÛÛปÛÛบ ÛÛษผ
echo                        ÛÛÛÛÛÛÛปÛÛÛÛÛÛÛบÛÛÛÛÛÛÛบÛÛÛÛÛÛษผÛÛÛÛÛษผ
echo                        ศออออÛÛบÛÛษออÛÛบÛÛษออÛÛบÛÛษออÛÛปÛÛษอÛÛป
echo                        ÛÛÛÛÛÛÛบÛÛบ ÛÛบÛÛบ ÛÛบÛÛบ ÛÛบÛÛบ ÛÛป
echo                        ศออออออผศอผ ศอผศอผ ศอผศอผ ศอผศอผ ศอผ
echo.
color 0C
echo                              ÛÛÛÛÛÛป ÛÛÛÛÛÛÛปÛÛÛÛÛÛป ÛÛÛÛÛÛÛÛปÛÛÛÛÛÛÛป ÛÛÛÛÛป ÛÛÛป ÛÛÛป
color 0E
echo                              ÛÛษออÛÛปÛÛษออออผÛÛษออÛÛป ศออÛÛษออผÛÛษออออผÛÛษออÛÛปÛÛÛÛป ÛÛÛÛบ
color 0A
echo                              ÛÛÛÛÛÛษผÛÛÛÛÛป ÛÛÛÛÛÛษผ ÛÛบ ÛÛÛÛÛป ÛÛÛÛÛÛÛบÛÛษÛÛÛÛษÛÛบ
color 0B
echo                              ÛÛษออÛÛปÛÛษออผ ÛÛษออÛÛป ÛÛบ ÛÛษออผ ÛÛษออÛÛบÛÛบศÛÛษผÛÛบ
color 0D
echo                              ÛÛบ ÛÛบÛÛÛÛÛÛÛปÛÛบ ÛÛบ ÛÛบ ÛÛÛÛÛÛÛปÛÛบ ÛÛบÛÛบ ศอผ ÛÛบ
color 0A
echo                              ศอผ ศอผศออออออผศอผ ศอผ ศอผ ศออออออผศอผ ศอผศอผ ศอผ
echo.
color 0C
echo                        อออออออออออออออออออออออออออออออออออออออออออออออ
echo                        บ    LAUNCHER RED TEAM OFICIAL DE SHARK       บ
echo                        อออออออออออออออออออออออออออออออออออออออออออออออออ
echo.
color 0A
echo                        [1] Ejecutar script Python (carpeta actual)
echo                        [2] Levantar servidor HTTP Python
echo                        [3] Salir
echo.
set /p choice=Selecciona tu arma, SHARK (1-3): 

if "%choice%"=="1" goto LIST_PY
if "%choice%"=="2" goto SERVER_PY
if "%choice%"=="3" goto END
color 0C
echo   [!] Opciขn inv lida, tiburขn...
timeout /t 1 >nul
goto LOGO

:: ================== RESTO DEL CเDIGO (igual que antes) ==================
:LIST_PY
cls
color 0B
echo ษออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออป
echo บ                  SCRIPTS PYTHON DETECTADOS                                   บ
echo ศออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออผ
echo.
set count=0
for %%f in (*.py) do (
    set /a count+=1
    set "script[!count!]=%%f"
    echo   [!count!] %%f
)
if %count%==0 (
    echo   [!] No hay scripts .py. Mete tus armas aquก.
    pause
    goto LOGO
)
echo.
set /p num=Elige nฃmero (0 = volver): 
if "%num%"=="0" goto LOGO
if defined script[%num%] (
    color 0A
    echo.
    echo  [>>] Ejecutando !script[%num%]! ...
    python "!script[%num%]!"
    pause
)
goto LOGO

:SERVER_PY
cls
color 0E
echo ษออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออป
echo บ                     SERVIDOR HTTP PYTHON                                     บ
echo ศออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออออผ
echo.
set /p port=จPuerto, jefe? (Enter = 8000): 
if "%port%"=="" set port=8000
echo.
echo  [>>] Servidor activo ? http://0.0.0.0:%port%
echo  [>>] Ctrl+C para parar
echo.
python -m http.server %port%
pause
goto LOGO

:END
cls
color 0C
echo.
echo                     ญNos vemos en la prขxima caza, SHARK!
timeout /t 3 >nul
exit