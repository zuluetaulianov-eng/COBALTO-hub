@echo off
title Venezuela Noticias — Subir Repositorio a GitHub
color 0A
cls
echo ==================================================================
echo   🇻🇪 SUBIR VENEZUELA NOTICIAS A GITHUB COMO PROYECTO INDEPENDIENTE
echo ==================================================================
echo.
echo Paso 1: Crea un nuevo repositorio vacio en GitHub (sin README ni .gitignore).
echo        Sugerencia de nombre: venezuela-noticias
echo.
echo URL por defecto: https://github.com/zuluetaulianov-eng/venezuela-noticias.git
echo.

set /p REPO_URL="Pega la URL de tu repositorio de GitHub (o presiona ENTER para usar la URL por defecto): "

if "%REPO_URL%"=="" (
    set REPO_URL=https://github.com/zuluetaulianov-eng/venezuela-noticias.git
)

echo.
echo Configurando remoto origin: %REPO_URL% ...

git remote remove origin >nul 2>&1
git remote add origin %REPO_URL%
git branch -M main

echo.
echo Subiendo código a GitHub (git push -u origin main)...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==================================================================
    echo   [EXITO] ¡Proyecto subido correctamente a GitHub!
    echo   Repositorio: %REPO_URL%
    echo ==================================================================
) else (
    echo.
    echo ==================================================================
    echo   [AVISO] Si aún no has creado el repositorio en GitHub,
    echo   ve a https://github.com/new y créalo con el nombre "venezuela-noticias".
    echo   Luego vuelve a ejecutar este script.
    echo ==================================================================
)

echo.
pause
