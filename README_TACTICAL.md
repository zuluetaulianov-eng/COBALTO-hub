# 🛰️ COBALTO HUB v9.0 - Guía de Despliegue Táctico

Este repositorio contiene la plataforma de inteligencia **Cobalto Hub**. Sigue estas instrucciones para iniciar el despliegue en tu estación de trabajo.

## 📋 Requisitos Previos
- **Python 3.10+**
- **Google Chrome** (Para módulos de scraping avanzados y Playwright)

## 🚀 Inicio Rápido

### En Windows
1. Haz doble clic en `start_cobalto.bat`.
2. El sistema verificará automáticamente las dependencias e iniciará el servidor.
3. Accede a: `http://127.0.0.1:8083`

### En Linux / macOS
1. Abre una terminal en la carpeta del proyecto.
2. Otorga permisos de ejecución al script:
   ```bash
   chmod +x start_cobalto.sh
   ```
3. Ejecuta el script:
   ```bash
   ./start_cobalto.sh
   ```
4. Accede a: `http://127.0.0.1:8083`

## 🛠️ Modos de Ejecución
- **Producción (Normal):** Ejecuta el script sin argumentos.
- **Desarrollo (Auto-reload):** Ejecuta el script con el argumento `--dev`.
  - Windows: `start_cobalto.bat --dev`
  - Linux/Mac: `./start_cobalto.sh --dev`

## 📱 Capacidades PWA
Cobalto Hub es ahora una **Progressive Web App**. 
- Una vez iniciado el servidor, puedes "Instalar" la aplicación desde la barra de direcciones de Chrome/Edge.
- Esto permitirá el uso de la interfaz en modo offline y acceso directo desde el escritorio.

---
**NOTA DE SEGURIDAD:** Este sistema utiliza un Escudo DoH (DNS over HTTPS) integrado para evadir censura regional. No requiere configuración adicional.
