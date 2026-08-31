# 📹 SUBSISTEMA DE EXPORTACIÓN Y VIGILANCIA DE VIDEO — COBALTO HUB

Este paquete es un **módulo independiente, autónomo y desacoplado** de la estructura del sistema COBALTO HUB para la **captura, procesamiento, visión artificial por computadora (Computer Vision), streaming y visualización de video / CCTV en tiempo real** en un Dashboard táctico.

---

## 🌟 Propósito y Diseño

Diseñado específicamente para **facilitar su extracción e integración en cualquier otro sistema**, este paquete incluye:
- **Motor de Ingesta & Streaming de Video**: Gestión de transmisiones MJPEG, flujos RTSP/HLS, cámaras Hikvision ISAPI, Dahua ONVIF, EZVIZ y extracción de enlaces de redes sociales (TikTok, Instagram, YouTube, Vimeo).
- **Recolector de Fotogramas & Análisis de Movimiento (`cctv_collector.py`)**: Monitorización asíncrona concurrente, guardado de instantáneas con rotación automática, cálculo de deltas de movimiento por variación de píxeles y generación de alertas tácticas.
- **Módulo de Visión Artificial OpenCV (`cctv_vision.py`)**: Detección en tiempo real de peatones/personas (SVM HOG Descriptor), sustracción de fondo para análisis de movimiento (MOG2), estimación de densidad de tráfico vehicular y detección de anomalías.
- **Ingesta de Noticias con Video (`news_video_collector.py`)**: Extracción y curaduría de noticias periodísticas y reportes de redes sociales que contienen reproducciones multimedia (YouTube, TikTok, Vimeo, Telegram, MP4), listas para filtrado por país y categoría.
- **Panel Dashboard Front-End Táctico (`cctv_player.js` + `index.html` + `dashboard.css`)**: Cuadrícula dinámica CCTV con selector de layout (1×1, 2×2, 3×3, 4×4), módulo de Noticias con Video, modal de expansión full-screen, panel lateral de metadatos (FPS, latencia, resolución) y reproductor multimedia.
- **Servidor Autónomo FastAPI (`main.py` + `router.py`)**: Servidor independiente listo para ejecutar con 1-clic o importar como `APIRouter` en cualquier framework Python existente.

---

## 📁 Estructura del Sistema (VIDEO EXPORT)

```text
VIDEO EXPORT/
├── README.md                      # Documentación completa de arquitectura e integración
├── start.bat                      # Lanzador automático 1-Clic para Windows
├── requirements.txt               # Dependencias Python (FastAPI, OpenCV, Pillow, aiohttp, etc.)
├── main.py                        # Punto de entrada del servidor FastAPI autónomo (Puerto 8090)
├── router.py                      # Router API REST con todos los endpoints de video, CCTV y noticias
├── video_engine.py                # Motor de procesamiento de video, streaming MJPEG y extracción
├── cctv_collector.py              # Recolector de instantáneas, control de lista de seguimiento y deltas
├── cctv_vision.py                 # Analizador de Visión por Computadora (OpenCV HOG + MOG2)
├── news_video_collector.py        # Colector y curador de noticias con reproducción de video
├── static/
│   ├── css/
│   │   └── dashboard.css          # Hoja de estilos táctica ciberpunk (Glassmorphism, temas)
│   └── js/
│       └── cctv_player.js         # Módulo Frontend JS (Grid, Modal, Noticias con Video, Extractor)
├── templates/
│   └── index.html                 # Plantilla Jinja2 del Dashboard Táctico de Video
├── data/
│   └── cctv_snapshots/            # Almacenamiento local de fotogramas e historial
└── tests/
    └── test_video_export.py       # Suite de pruebas automatizadas con pytest
```

---

## ⚙️ Arquitectura y Flujo de Datos

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          FUENTES DE VIDEO & CCTV                                │
│   [Cámaras NVR Hikvision/Dahua]   [Servidores MJPEG/HLS]   [Feeds Sociales/MP4]   │
└────────────────────────┬────────────────────────────────────────┬───────────────┘
                         │                                        │
                         ▼                                        ▼
┌──────────────────────────────────────────────┐ ┌────────────────────────────────┐
│   cctv_collector.py (Async Fetcher)          │ │  video_engine.py               │
│   - Captura continua de instantáneas JPEGs    │ │  - Extractor de enlaces video  │
│   - Rotación y guardado en data/snapshots/   │ │  - Generador de stream MJPEG   │
└────────────────────────┬─────────────────────┘ └────────────────┬───────────────┘
                         │                                        │
                         ▼                                        │
┌──────────────────────────────────────────────┐                          │
│   cctv_vision.py (OpenCV Computer Vision)    │                          │
│   - Detección de Peatones (HOG SVM)          │                          │
│   - Sustracción MOG2 & Movimiento            │                          │
│   - Clasificación Densidad & Anomalías        │                          │
└────────────────────────┬─────────────────────┘                          │
                         │                                        │
                         └───────────────────┬────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              router.py (FastAPI)                                │
│    GET /api/cctv/grid   |   GET /api/cctv/stream/{id}   |   POST /api/vision    │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    DASHBOARD FRONTEND (cctv_player.js)                          │
│    - Grid Toggle (1x1 a 4x4)      - Vision Overlay     - Modal Fullscreen      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Instalación y Ejecución Rápida (Standalone)

### 1. Requisitos Previos
- Python 3.11 o superior.
- `pip` actualizado.

### 2. Instalación de Dependencias
```bash
pip install -r requirements.txt
```

### 3. Iniciar Servidor (Windows 1-Clic)
Doble clic sobre el archivo `start.bat` o desde CMD/PowerShell:
```cmd
start.bat
```

### 4. Iniciar mediante Línea de Comandos
```bash
python main.py --port 8090
```

Navega en tu navegador a:
- 🌐 **Dashboard Táctico de Video**: `http://localhost:8090/`
- 📡 **Estado de Servidor / Salud**: `http://localhost:8090/health`
- 📖 **Documentación Swagger API**: `http://localhost:8090/docs`

---

## 🔌 Guía de Integración en Otro Sistema

Existen **3 formas principales** de integrar este módulo en otro sistema existente:

### Opciones de Integración

#### Opción A: Microservicio Independiente (Recomendado)
Mantén ejecutando este módulo en el puerto `8090` mediante `python main.py` o dentro de un contenedor Docker/servicio systemd.
- **Integración Web**: Inserta el dashboard mediante un `<iframe>` en tu sistema existente:
  ```html
  <iframe src="http://localhost:8090/" style="width:100%; height:800px; border:none;"></iframe>
  ```
- **Consumo API REST**: Realiza peticiones HTTP `GET http://localhost:8090/api/cctv/cameras` desde cualquier lenguaje (Node.js, PHP, Java, Python, Go) para obtener las cámaras y sus fotogramas.

#### Opción B: Integración Directa en un Servidor FastAPI / Python Existente
Copia los archivos `video_engine.py`, `cctv_collector.py`, `cctv_vision.py` y `router.py` en el proyecto destino e incluye el router en la aplicación principal:

```python
from fastapi import FastAPI
from router import video_router

app = FastAPI(title="Mi Sistema Principal")

# Registrar las rutas del módulo de video
app.include_router(video_router, prefix="/api/video", tags=["Video Subsystem"])
```

#### Opción C: Integración del Componente Frontend en un Dashboard Existente
1. Incluye las hojas de estilo `dashboard.css` y el script `cctv_player.js` en las plantillas HTML de tu sistema.
2. Añade el contenedor HTML objetivo en tu vista:
   ```html
   <div id="cctv-grid-container"></div>
   ```
3. Inicializa el componente JavaScript apuntando a los endpoints de video:
   ```javascript
   document.addEventListener('DOMContentLoaded', () => {
       window.VideoPlayerSubsystem.init({
           containerId: 'cctv-grid-container',
           apiBaseUrl: '/api/video'
       });
   });
   ```

---

## 📡 Referencia de Endpoints API REST

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/cctv/cameras` | Devuelve el catálogo completo de cámaras registradas y su estado online/offline |
| `GET` | `/api/cctv/stream/{camera_id}` | Transmite flujo continuo de imágenes MJPEG (Motion JPEG) de la cámara especificada |
| `GET` | `/api/cctv/frame/{camera_id}` | Obtiene el último fotograma JPEG disponible en almacenamiento local |
| `POST` | `/api/cctv/analyze/{camera_id}` | Ejecuta el motor de Visión Artificial OpenCV sobre la cámara y devuelve conteo de personas, tráfico y detección de anomalías |
| `GET` | `/api/cctv/alerts` | Devuelve la lista de alertas por movimiento y actividad en tiempo real |
| `POST` | `/api/cctv/watchlist/add` | Añade una cámara a la lista de seguimiento táctico prioritario |
| `POST` | `/api/video/extract` | Analiza un enlace de video (TikTok, Instagram, YouTube, MP4 direct) y extrae la URL directa reproducible |
| `GET` | `/api/news/videos` | Devuelve las noticias periodísticas y publicaciones que incluyen video reproducible |
| `POST` | `/api/news/videos/push` | Registra una nueva noticia con video incorporado en la bandeja del subsistema |

---

## 🛡️ Prevención y Manejo de Bloqueos del Explorador (CORS, Mixed Content & Autoplay)

Al integrar reproducción de video, CCTV y noticias multimedia en navegadores web modernos (Chrome, Firefox, Edge, Safari, Brave), se pueden presentar bloqueos de seguridad nativos del navegador. El subsistema **VIDEO EXPORT** resuelve activamente estos escenarios mediante los siguientes mecanismos:

### 1. Bloqueo por Contenido Mixto (*Mixed Content* HTTP vs HTTPS)
- **Escenario**: Si el dashboard o sistema anfitrión se ejecuta bajo protocolo seguro `https://`, los exploradores bloquean de forma estricta transmisiones de cámaras NVR o feeds HTTP directos (`http://cctv.local/stream`).
- **Solución en VIDEO EXPORT**: El servidor backend (`video_engine.py`) actúa como proxy intermedio de transporte. El explorador solo solicita endpoints locales del subsistema (`/api/cctv/stream/{id}` y `/api/cctv/frame/{id}`), eliminando la restricción de contenido mixto.

### 2. Bloqueo por Políticas CORS y `X-Frame-Options: SAMEORIGIN`
- **Escenario**: Portales de noticias y servidores de video aplican la cabecera HTTP `X-Frame-Options: DENY` o `SAMEORIGIN`, impidiendo incrustar sus vistas en un `<iframe>` dentro de otro sistema.
- **Solución en VIDEO EXPORT**: El colector normaliza las URLs a dominios de incrustación permitidos (ej. `youtube-nocookie.com/embed/...`, `player.vimeo.com`, `tiktok.com/embed/v2`) o realiza extracción directa del flujo de video (`.mp4`, `.m3u8`), permitiendo la reproducción fluida sin ser bloqueado por politicas de iframe.

### 3. Restricciones de Reproducción Automática (*Autoplay Policy*)
- **Escenario**: Los exploradores bloquean elementos `<video autoplay>` que contengan audio si no ha habido interacción directa del usuario en el documento.
- **Solución en VIDEO EXPORT**: Las señales en vivo de la cuadrícula CCTV utilizan reproducción silenciada (`muted autoplay`), mientras que los videos de noticias y extractores sociales se activan por evento de usuario (clic en tarjeta o botón de reproducción en el modal táctico).

### 4. Bloqueo por Filtros Anti-Rastreo y AdBlockers
- **Escenario**: Extensiones como uBlock Origin, Privacy Badger o Brave Shields bloquean reproductores que incluyen scripts de telemetría de redes sociales.
- **Solución en VIDEO EXPORT**: Se utilizan URLs de incrustación desacopladas sin cookies de seguimiento y reproductores HTML5 nativos para evitar ser bloqueados por filtros publicitarios.

---

## 🧪 Pruebas Unitarias

Para validar la correcta funcionalidad de la ingesta de video, visión artificial y endpoints:

```bash
python -m pytest tests/test_video_export.py -v
```

---

## 📄 Licencia y Créditos

Desarrollado como módulo táctico de exportación dentro del ecosistema **COBALTO HUB**.
Licencia MIT — Libre para integración, modificación y despliegue en sistemas externos.
