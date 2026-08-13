@echo off
title Ollama Chat - IA Local
color 0B
cls
echo.
echo  =========================================================
echo    OLLAMA CHAT  ^|  Interfaz de Pruebas IA
echo    Servidor por defecto: 192.168.1.213:11434
echo  =========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo  [ERROR] Python no esta instalado o no esta en el PATH.
    echo  Instala Python desde python.org o la Microsoft Store.
    echo.
    pause
    exit /b
)

echo  Iniciando interfaz grafica...
echo  Puedes cerrar esta ventana despues de que aparezca la interfaz.
echo.

python -c "import docx, PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [INFO] Instalando dependencias para exportar informes...
    pip install python-docx pillow
)

start "" python "%~dp0chat_ollama.py"
timeout /t 2 /nobreak >nul
exit
