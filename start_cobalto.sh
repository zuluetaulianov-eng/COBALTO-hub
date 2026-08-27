#!/bin/bash

# COBALTO HUB v15.2 - Instalador & Bootstrapper Automatizado (Linux/macOS)
CYAN='\033[0;36m'
BRIGHT_CYAN='\033[1;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

clear

echo -e "${BRIGHT_CYAN}"
echo "   ==================================================="
echo "            C O B A L T O   H U B   v 1 5 . 2"
echo "        Instalador de Entorno y Lanzador Dual"
echo "   ==================================================="
echo -e "${NC}"

# --- 1. VERIFICAR INSTALACIÓN DE PYTHON ---
echo -e " [${CYAN}+${NC}] Verificando runtime de Python compatible..."

PYTHON_CMD=""

if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

# Intentar instalar Python automáticamente si no existe
if [ -z "$PYTHON_CMD" ]; then
    echo -e " [${YELLOW}ALERTA${NC}] Python no se encuentra instalado en el sistema."
    
    # Detectar el gestor de paquetes de Linux
    if command -v apt-get &> /dev/null; then
        echo -e " [${CYAN}+${NC}] Detectado gestor APT (Ubuntu/Debian). Instalando Python3..."
        sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
        PYTHON_CMD="python3"
    elif command -v brew &> /dev/null; then
        echo -e " [${CYAN}+${NC}] Detectado gestor Homebrew (macOS). Instalando Python3..."
        brew install python
        PYTHON_CMD="python3"
    elif command -v dnf &> /dev/null; then
        echo -e " [${CYAN}+${NC}] Detectado gestor DNF (Fedora/RHEL). Instalando Python3..."
        sudo dnf install -y python3 python3-pip
        PYTHON_CMD="python3"
    else
        echo -e "${RED} [ERROR] No se pudo instalar Python de forma automatizada. Por favor, instale Python 3.10+ manualmente.${NC}"
        exit 1
    fi
fi

# --- 2. VERIFICAR COMPATIBILIDAD DE VERSION DE PYTHON ---
# Comprobar que sea al menos Python 3.10
$PYTHON_CMD -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" &> /dev/null
if [ $? -ne 0 ]; then
    echo -e " [${YELLOW}ALERTA${NC}] Se detectó una versión obsoleta de Python. Requiere Python 3.10 o superior."
    
    if command -v apt-get &> /dev/null; then
        echo -e " [${CYAN}+${NC}] Actualizando a Python3 moderno..."
        sudo apt-get update && sudo apt-get install -y python3
    elif command -v brew &> /dev/null; then
        echo -e " [${CYAN}+${NC}] Actualizando Python a través de Homebrew..."
        brew upgrade python
    else
        echo -e "${RED} [ERROR] Versión incompatible. Por favor, instale Python 3.10+ manualmente.${NC}"
        exit 1
    fi
fi

echo -e " [${GREEN}OK${NC}] Entorno de Python verificado: compatible."
echo ""

# --- 3. VERIFICAR E INSTALAR DEPENDENCIAS DEL PROYECTO ---
echo -e " [${CYAN}+${NC}] Verificando dependencias y librerías del sistema..."
$PYTHON_CMD check_deps.py
if [ $? -ne 0 ]; then
    echo -e "${RED} [ERROR] Verificación o instalación automática de librerías fallida.${NC}"
    exit 1
fi
echo ""

# --- 4. INICIAR LANZADOR GRÁFICO (GUI) ---
echo -e " [${GREEN}+${NC}] Todo listo. Abriendo Panel de Control Gráfico de COBALTO..."
$PYTHON_CMD cobalto_gui_launcher.py "$@"
