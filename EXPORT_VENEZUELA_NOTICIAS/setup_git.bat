@echo off
title Venezuela Noticias — Inicializador de Repositorio GitHub
color 0A
cls
echo ==================================================================
echo   🇻🇪 PREPARANDO REPOSICIÓN GIT PARA VENEZUELA NOTICIAS  
echo ==================================================================
echo.

git init
git add .
git commit -m "Initial commit: Venezuela Noticias standalone portal & CMS"

echo.
echo ==================================================================
echo   [OK] Repositorio Git local inicializado con éxito.
echo.
echo   Para subir a tu repositorio en GitHub, ejecuta los comandos:
echo.
echo   git remote add origin https://github.com/TU_USUARIO/venezuela-noticias.git
echo   git branch -M main
echo   git push -u origin main
echo ==================================================================
echo.
pause
