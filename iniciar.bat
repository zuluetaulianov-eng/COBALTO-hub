@echo off
python check_deps.py
if errorlevel 1 (
    echo Error al verificar dependencias
    pause
    exit /b 1
)
python dashboard.py
pause