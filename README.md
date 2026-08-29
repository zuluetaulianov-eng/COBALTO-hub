# 🛰️ COBALTO HUB — Plataforma de Inteligencia OSINT C4I v16.3

> **Sistema de Mando y Control de Inteligencia (C4I)** en tiempo real con **Arquitectura Multipaís (Multi-Theater OSINT)**,  
> **Target Dossier Engine (360° Risk Score)**, **Módulos OSINT Estatales Venezolanos (IVSS / SENIAT RIF / SAIME Institucional / CNE OSINT + Votación)**, **Streaming de Video Continuo HLS.js en Visor CCTV**, **Pivot de Inteligencia en Grafo Táctico**, **TLS Fingerprinting Evasion (JA3/HTTP2)**, **Singleton Browser Pool Manager**, **Visión Táctica CCTV 100% Real & Motor Proxy Resiliente**, **Extracción Semántica JSON-LD/OpenGraph**, **Reproducción de Video Táctico Nativa (Flutter/Web)**, **Persistencia Histórica Deduplicada**, **OSIRIS Diagnostic Doctor Engine**, **Zero-Key Semantic Web Search & Jina Reader** y **Blue Force Tracking (BFT)** — monitoreo de operadores en terreno, inteligencia global, RECON toolkit, OFAC SDN, CCTV y más.  
> Consolida fuentes RSS, canales de Telegram, redes sociales, ciberseguridad, rastreo de aeronaves/buques, telemetría de campo en vivo y análisis geopolítico multiagente con IA.  
> **v16.3** — Integración de **Fallback Histórico de Centros de Votación del CNE vía Wayback Machine (CDX API)** en `osint_cne.py` y `osiris-recon.js` para recuperación de Registro Electoral por Cédula, módulo OSINT Institucional CNE (comunicados, avisos oficiales y normativa), integración OSINT Institucional SAIME (movilidad fronteriza y trámites), reconstrucción OSINT Institucional IVSS (pensiones, salud y comunicados), reconstrucción OSINT Institucional SENIAT (API REST, Unidad Tributaria y RIF público), reproductor HLS.js integrado en visor CCTV, navegación pivot 1-clic en Grafo Táctico y suite completa de pruebas pasadas al 100%.

---

## 🔄 Últimas Actualizaciones (Agosto 2026 — Release v16.3)

- **🗳️ Recuperación de Centros de Votación CNE vía Wayback Machine (`osint_cne.py` & `osiris-recon.js`):**
  - **Motor Fallback CDX API**: `cne_voter_wayback_lookup(cedula)` realiza búsquedas dirigidas en los índices archivados del Internet Archive (Wayback Machine) sobre las URLs históricas del Registro Electoral del CNE (`ce.php?nacionalidad=V&cedula=...`).
  - **Parser HTML con Resiliencia Estructural (`parse_cne_voter_html`)**: Extrae y descompone datos de identidad e infraestructura de votación (*Nombre, Cédula, Estado, Municipio, Parroquia, Centro de Votación, Dirección y Mesa*).
  - **Filtro y Alertas de Diagnóstico**: En caso de no existir captura indexada para un documento, la UI informa claramente el estatus (`SIN_REGISTRO_ARCHIVADO`) y orienta sobre la alternativa **Opción A (Base de Datos Local SQLite en `data/cne_registro_electoral.db`)**.
  - **Interfaz Táctica OSIRIS RECON**: Tab actualizado a **`CNE OSINT / Votación`** con buscador paramétrico por cédula (ej. `V-12345678`), visualización de tarjetas geográficas y enlace directo al snapshot web original archivado.
- **🗳️ Módulo OSINT Institucional CNE (`osint_cne.py` & `osiris-recon.js`):**
  - Inteligencia **a nivel institucional público** del Consejo Nacional Electoral (CNE) de Venezuela: ingesta de **comunicados y noticias oficiales**, **avisos oficiales (actos públicos + PDFs `ao_documents`)** y catálogo de secciones institucionales (normativa electoral, gacetas, resultados agregados por mesa).
  - **Cauce vivo + fallback Wayback Machine:** intenta primero el portal oficial (`cne.gov.ve`); si está inaccesible, ingesta el snapshot archivado (API CDX) con normalización de enlaces (`_normalize_link`).
  - Clasificador heurístico por categorías (convocatoria, resultados, normativa, aviso oficial, institucional/institucional diplomático) y `CircuitBreaker` adaptativo de 10 minutos.
  - Sensor de *Radar Social* `get_cne_data()` (`dashboard_sensors.py`), endpoint `GET /api/osiris/recon/cne` (parámetros `scope` y `cedula`) y botón de pivot en el Grafo Táctico (`intel-graph.js`).
- **🏛️ Extractor OSINT Institucional IVSS (`osint_ivss.py` & `osiris-recon.js`):**
  - Inteligencia **a nivel institucional público** del Instituto Venezolano de los Seguros Sociales: ingesta de comunicados oficiales, clasificación de **alertas de pensiones/pagos**, **salud** y **trámites/servicios**, con catálogo de servicios oficiales.
  - Parser real del portal oficial (carrusel de comunicados + fechas), clasificador heurístico por categorías y `CircuitBreaker` adaptativo de 10 minutos.
  - **Alcance responsable:** el portal público IVSS no expone expedientes individuales. Este módulo NO fabrica ni consulta datos personales; los documentos (`V-`/`E-`) solo reciben validación estructural de formato.
  - Ingesta automática en el sensor de *Radar Social* (`dashboard_sensors.py`) y endpoint `GET /api/osiris/recon/ivss` (parámetros opcionales `cedula` y `scope`).
- **🏛️ Módulo OSINT Institucional SENIAT (`osint_seniat.py` & `osiris-recon.js`):**
  - Reconstruido como **herramienta OSINT institucional** del Servicio Nacional Integrado de Administración Aduanera y Tributaria: ingesta de **comunicados oficiales** vía API REST WordPress (`/wp-json/wp/v2/posts`) con clasificación por categorías (fiscalización, digitalización, banca y alianzas, aduanas, tributario, institucional).
  - **Unidad Tributaria (UT) en tiempo real**: valor vigente **Bs. 43,00** + histórico de 8 providencias/gacetas oficiales.
  - **Calendario de obligaciones tributarias** (12 meses 2026) y catálogo de servicios oficiales.
  - Consulta pública de **RIF** (registro tributario institucional: razón social, condición IVA, retención) sin exponer datos personales.
  - Sensor `get_seniat_data()` con datos reales, endpoint `GET /api/osiris/recon/seniat/institucional` (parámetros `rif` y `scope`) y botón de pivot en el Grafo Táctico.
- **🛂 Módulo OSINT Institucional SAIME (`osint_saime.py` & `osiris-recon.js`):**
  - Inteligencia **a nivel institucional público** del Servicio Administrativo de Identificación, Migración y Extranjería (SAIME Venezuela): ingesta de comunicados y noticias oficiales, clasificación de **alertas de movilidad fronteriza** públicas y catálogo de servicios/trámites oficiales.
  - Cauce estructurado del portal oficial (feed RSS `/feed/` + lista institucional de noticias), con parsing BeautifulSoup, `CircuitBreaker` adaptativo de 10 minutos y bypass de errores SSL gubernamentales.
  - **Alcance responsable:** este módulo NO realiza perfilamiento de personas físicas (no consulta ni expone registros personales de ciudadanos). Los documentos (`V-`/`E-`) solo reciben validación estructural de formato.
  - Ingesta automática en el sensor de *Radar Social* (`dashboard_sensors.py`) y endpoint `GET /api/osiris/recon/saime` (parámetros opcionales `cedula` y `scope`).
  - Botón de pivot 1-clic en el Grafo Táctico (`intel-graph.js`).
- **📹 Streaming Video Continuo HLS.js para CCTV Grid & Modal (`templates/partials/_head.html` & `osiris-global.js`):**
  - Integración de `Hls.js` para la reproducción fluida de streams de video en tiempo real (`.m3u8`) en el visor CCTV de OSIRIS Global.
  - Conmutación inteligente entre fotogramas estáticos y reproductor HTML5 con control de errores y recuperación automática de cortes de búfer.
- **🕸️ Enlace Bi-direccional y Pivot OSINT en Grafo Táctico (`intel-graph.js`):**
  - Integración de botones de acción rápida en el panel de detalle de cualquier nodo en el Grafo Social: salto en 1-clic hacia las herramientas **IVSS Institucional**, **SENIAT RIF**, **SAIME Institucional** y **CNE Institucional** dentro de OSIRIS RECON.
- **🧪 Cobertura del 100% en Suite de Pruebas (`tests/`):** **191/191 tests pasados exitosamente**.

- **📹 Visión Táctica CCTV 100% Real & Motor Proxy Resiliente (`osiris_bridge.py` & `osiris-global.js`):**
  - **Política Cero Simulación:** Eliminación completa de generadores sintéticos. Las transmisiones muestran exclusivamente fuentes en vivo o un indicador SVG neutro de fuera de línea si la cámara cae en origen.
  - **Ingesta Paralela Asíncrona:** Integración de `asyncio.gather` para consultar simultáneamente más de 350+ cámaras de fuentes como TfL Londres, Singapur LTA, WSDOT Washington, NYC DOT TMC, Caltrans CA y redes LATAM (Venezuela/Colombia).
  - **Motor Proxy con Bypass TLS/SSL & Cabeceras de Navegador:** Conexión flexibilizada (`ssl=False`) para webcams públicas con certificados vencidos y emulación de cabeceras Chrome de escritorio para evadir bloqueos de WAF/Cloudflare.
  - **Exploración Adaptativa de Rutas IP:** Sondeo automático de subrutas estándar (`/mjpg/video.mjpg`, `/axis-cgi/mjpg/video.cgi`, `/video.mjpg`, `/image.jpg`) al conectar con hosts IP directos.
  - **Caché en Memoria Anti-Parpadeo (90s):** Almacenamiento de fotogramas válidos recientes en memoria para prevenir cortes visuales durante micro-caídas de red.
  - **Búsqueda Táctica Instantánea:** Barra de búsqueda en tiempo real por texto (`🔍 Search camera, city...`) para filtrar por ciudad, país o nombre de cámara sin recargar la página.
  - **Captura Táctica de Snapshots:** Botón **`📸 CAPTURAR SNAPSHOT`** en la barra lateral y en el visor fullscreen para descargar imágenes al instante con marca de agua UTC.
  - **Enlace Bi-direccional con Mapa Leaflet:** Botón **`📹 VER EN VISOR FULLSCREEN CCTV`** en popups de Leaflet y botón **`📍 MAPA`** en el visor global para saltar entre la vista geoespacial y el visor de video.

- **🩺 Motor de Diagnóstico Táctico `OSIRIS Doctor` (`osiris_bridge.py` & `osiris_recon.py`):**
  - Chequeos de salud concurrentes sobre 10 fuentes principales OSINT (DNS DoH, WHOIS RDAP, BGP ip-api, crt.sh, MITRE CVE, Shodan, GitHub, Leaks, AlienVault OTX, Jina Reader).
  - Botón táctico **`🩺 RUN DOCTOR`** e interfaz interactiva con matriz de disponibilidad de fuentes en tiempo real.
- **📖 Extractor Web Limpio Markdown via Jina Reader (`jina_web_read`):**
  - Conversión instantánea de portales web a Markdown para ingesta directa en el motor RAG / IA Core.
- **🔍 Búsqueda Web Semántica Zero-Key (`jina_web_search`):**
  - Búsqueda OSINT global libre de claves API mediante la API `s.jina.ai`.
- **📺 YouTube Intel & Transcriptor (`youtube_intel`):**
  - Extracción de metadatos oEmbed, thumbnails y subtítulos/transcripciones en texto plano/Markdown para investigación multimedia.
- **📡 Validador y Lector Directo de Feeds RSS/Atom (`rss_reader`):**
  - Ingesta directa y parsing de canales RSS/Atom desde el propio kit RECON.

- **🎬 Reproducción de Video Táctico Nativo en COBALTO Mobile (`cobalto_mobile`):**
  - **Widget `VideoPlayerSheet`:** Detección dinámica de streaming directo (MP4/HLS con `chewie` y `video_player`) vs. reproductores incrustados nativos (`youtube_player_flutter`).
  - **Tarjetas SitRep (`SitrepNewsCard`):** Badge táctico `🎥 MEDIA`, botón flotante de reproducción rápida sobre la miniatura e interacción directa vía botón `VIDEO`.
  - **Hoja de Detalle (`IntelDetailsSheet`):** Banner superior destacado para reproducción inmediata de contenido audiovisual adjunto a reportes de inteligencia.
  - **Persistencia SQLite v5 (`LocalDbService` & `LocalExtractorService`):** Actualización del esquema `cobalto_edge.db` para almacenar y consultar el campo `video` de forma offline.
- **🛡️ Motor Evasor TLS JA3/HTTP2 (`tls_evasion.py`):** Bypass de protecciones Cloudflare/Akamai/WAF mediante la simulación exacta de huellas digitales TLS de navegadores reales (`chrome_120`, `firefox_120`, `safari_16_0`) a velocidad de socket HTTP/2 sin la sobrecarga de un navegador pesado.
- **🌐 Singleton Browser Pool Manager (`browser_pool.py`):** Reutilización de contextos y pestañas Chromium con Playwright Stealth. Reducción del **70% de consumo en RAM** y aceleración de peticiones complejas a `< 1 segundo`.
- **🎬 Extractor Semántico Rico (JSON-LD & OpenGraph & Twitter Cards) (`extractor.py`):** Parsing automatizado de esquemas `<script type="application/ld+json">` (`NewsArticle`, `VideoObject`, `ImageObject`) y meta-tags `og:image`, `og:video` y `twitter:player`.
- **⚡ Circuit Breakers con Exponential Backoff & Jitter (`social_public_extractor.py`):** Control adaptativo de tasa de consultas con desambiguación aleatoria (*Jitter* 0-30s) para prevenir bloqueos por Rate Limit en redes sociales y buscadores.
- **🎥 Transcodificación HLS & Analítica de Video CCTV YOLOv8-Nano (`osiris_bridge.py`):**
  - `GET /api/osiris/cctv/stream`: Manifiestos `.m3u8` dinámicos para reproducción nativa HTML5 en navegador sin plugins.
  - `GET /api/osiris/cctv/analyze`: Detección en tiempo real de vehículos, peatones y densidad de tráfico con generación de alertas tácticas `ALERTA BFT`.
- **🧪 Cobertura del 100% en Suite de Pruebas (`tests/`):** **153/153 tests pasados exitosamente**.
- **🛡️ Deduplicación Canónica por Título & Persistencia Histórica Cross-Reboot (`dashboard_pipeline.py`, `historical_store.py`):** Firma canónica mediante hashes MD5 de títulos normalizados e ingesta deduplicada en base de datos SQLite persistente conservada entre reinicios.
- **🎥 Red de Vigilancia CCTV Global & Alerta Temprana por Visión Artificial (`osiris_bridge.py`, `cctv_snapshot_collector.py`):** Ingesta pública de **350+ cámaras simultáneas** abarcando 15+ países (Colombia, Venezuela, México, Argentina, Chile, Brasil, Perú, Ecuador, Panamá, España, Italia, Alemania, Rusia, Turquía, Japón, NYC DOT, Caltrans CA).
- **🇨🇴 Módulo de Extracción Teatro Colombia OSINT (`osiris_colombia_recon.py`):** Fuentes oficiales colombianas: **SECOP II**, **SIMCI / UNODC**, **JEP** y **Rama Judicial**.
- **📱 Integración Visual en COBALTO Mobile (`MapMarkerDetailsSheet` & `cobalto_api_service.dart`):** Marcadores amarillos pulsantes (`#FFD60A`), hoja de detalles táctica con insignias `🔴 LIVE STREAM OSIRIS` y visor de video integrado en vivo.

---

## 📐 Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│  cobalto_worker.py  ──► extrae OSINT ──► escribe caché      │
│                     ──► historical_store.py (SQLite 90d)   │
│                     ──► event_bus.py (pub/sub interno)     │
│  (proceso independiente)          dashboard_persistent_cache.json
│                                              │  Redis (opcional)
│  app.py (FastAPI)   ◄── lee caché ──────────┘               │
│  (servidor puro)    ──► WebSocket ──► browser (index.html)  │
│                     ──► /api/export/sitrep (JSON)           │
│                     ──► /api/export/sitrep/docx (DOCX)      │
│                     ──► /api/export/sitrep/pdf (PDF)        │
│                     ──► /api/export/sitrep/analizar (IA)    │
│                     ──► /api/export/sitrep/generar-word     │
│                     ──► /api/export/sitrep/generar-pdf      │
│                     ──► /api/historical?timestamp=T         │
│                     ──► /api/historical/range?from=&to=     │
│                     ──► /api/historical/stats               │
│                     ──► /api/notes (CRUD anotaciones)       │
│                     ──► /api/health/sources                 │
│  ┌─ OSIRIS Engine ──────────────────────────────────────┐   │
│  │  osiris_bridge.py ──► /api/osiris/* (33 endpoints)    │   │
│  │  ├─ /api/osiris/recon/*  (16 tools)                   │   │
│  │  ├─ /api/osiris/data/*   (CCTV, SIGINT)              │   │
│  │  ├─ /api/osiris/intel/*  (Wikidata SPARQL)           │   │
│  │  ├─ /api/osiris/sanctions/* (OFAC SDN lookup)        │   │
│  │  └─ /api/osiris/health                               │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌─ Entity Knowledge Graph ─────────────────────────────┐   │
│  │  entity_resolver.py ──► fuzzy match                  │   │
│  │  entity_registry.py ──► canonical store              │   │
│  │  entity_linker.py ────► social ↔ OFAC ↔ Wikidata     │   │
│  │  historical_store.py ──► SQLite mensual (90d)        │   │
│  │  event_bus.py ─────────► pub/sub interno             │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌─ Flujos Agénticos IA ───────────────────────────────┐   │
│  │  agent_tools.py ──────────► 9 tools OSIRIS envueltas │   │
│  │  ares_investigator.py ────► detective autónomo       │   │
│  │  agent_orchestrator.py ───► cola/planificación       │   │
│  │  agent_memory.py ─────────► sesiones persistentes    │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌─ Alerta Temprana Predictiva ────────────────────────┐   │
│  │  predictive_scorer.py ────► scoring 5 señales        │   │
│  │  early_warning.py ────────► 10 reglas de escalado    │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌─ FININT & Dark Web ────────────────────────────────┐   │
│  │  finint_blockchain.py ───► monitoreo BTC/ETH        │   │
│  │  finint_darkweb.py ───────► análisis texto + paste   │   │
│  │  finint_entity_linker.py ─► wallets→entity registry  │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌─ HUMINT & Edge Computing ──────────────────────────┐   │
│  │  humint_bot.py ───────────► Telegram field reports   │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌─ CCTV Snapshot Collector ──────────────────────────┐   │
│  │  cctv_snapshot_collector.py ──► snapshots disco     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

| Componente | Descripción |
|---|---|
| `app.py` | Servidor FastAPI. Solo sirve datos y UI. No extrae. |
| `cobalto_worker.py` | Worker independiente. Ejecuta ciclos OSINT fast/full/heavy. |
| `ai_core.py` | Motor de debate tripartito: ARES · MINERVA · NEXUS + COORD. |
| `social_hub.py` | Orquestador unificado de extracción de redes sociales. |
| `social_public_extractor.py` | Extractor HTTP público (nitter, foros, dorks). |
| `database.py` | Capa de persistencia políglota (SQLite / PostgreSQL), incluye `card_notes` para anotaciones. |
| `config.py` | Configuración dinámica centralizada (feeds, umbrales, IA). Persiste en `config_dynamic.json` + BD. |
| `config_dynamic.json` | Archivo de configuración generado dinámicamente desde el panel vía `POST /api/config`. |
| `config_manager.js` | Controlador frontend del panel de configuración (8 subtabs, 50+ parámetros editables). |
| `seismic_monitor.py` | Monitor sísmico USGS con geocerca Haversine y dedup persistente en SQLite. |
| `gdacs_monitor.py` | Monitor de alertas de desastres GDACS (ONU): ciclones, inundaciones, incendios, volcanes. |
| `flight_tracker.py` | Rastreo ADS-B de aeronaves + detección de emergencias (Squawk 7700/7600/7500). |
| `asn_monitor.py` | Monitoreo de apagones de internet (IODA/Georgia Tech) sobre ASNs críticos venezolanos con modelo de ventanas deslizantes. |
| `correlation_engine.py` | Correlación geoespacial por Haversine: cruza sismos, apagones, GDACS y eventos de seguridad. |
| `telegrambot.py` | Bot C4I con comandos `/status`, `/alerts`, `/search`, `/outages`, `/briefing` + RSS broadcast. |
| `user_search.py` | Búsqueda multi-plataforma con monitor de cambios en perfiles de targets. |
| `export_sitrep_docx.py` | Generación de documentos Word (.docx) del SitRep con plantilla Jinja2/docxtpl. |
| `export_sitrep_ia.py` | Análisis IA NVIDIA (Deepseek) por entrada OSINT: actores, amenaza y análisis estratégico. |
| `export_sitrep_pdf.py` | Generación de PDF profesional del SitRep vía fpdf2 con tabla de alertas, outages y briefing. |
| `scripts/create_sitrep_template.py` | Generador de la plantilla DOCX `template_sitrep.docx` con marcadores Jinja2. |
| `osiris_bridge.py` | Router FastAPI con 33 endpoints `/api/osiris/*`: RECON, Intel, Sanctions, Data, Health. |
| `osiris_recon.py` | RECON toolkit: 16 herramientas OSINT (DNS, WHOIS, BGP, CVE, Shodan, MAC, Phone, GitHub, Leaks, IP, Threats, SSL, Headers, Certs, IP Intel, Network Sweep). |
| `osiris_intel.py` | Motor de inteligencia: OFAC SDN (OpenSanctions) + Wikidata SPARQL resolver + sanciones internacionales. |
| `entity_resolver.py` | Motor de fuzzy matching: Levenshtein + token-set ratio para resolución de nombres contra OFAC SDN. |
| `entity_registry.py` | Registro canónico de entidades SQLite con aliases, tipos, fuentes, tracking OFAC/Wikidata, asociación con snapshots. |
| `entity_linker.py` | Cross-source entity linker: corre en ciclo Heavy, cruza social graph + OFAC SDN + Wikidata contra el registry. |
| `historical_store.py` | Almacén histórico SQLite particionado por mes, retención 90 días para consultas temporales. |
| `event_bus.py` | Bus de eventos interno pub/sub (sin Redis) con bridge a WebSocket del dashboard. |
| `agent_tools.py` | Tool dataclass con 9 herramientas OSIRIS envueltas + rate limiting. |
| `ares_investigator.py` | Detective autónomo de anomalías (modos suggest/auto). |
| `agent_orchestrator.py` | Cola de tareas agénticas y planificación de ciclos. |
| `agent_memory.py` | Sesiones de agente persistentes SQLite con context window. |
| `predictive_scorer.py` | Motor de scoring probabilístico con 5 señales (composite/agent/exposure/recency/severity). |
| `early_warning.py` | Sistema de alerta temprana con 10 reglas de escalado + dedup 1h + supresión. |
| `finint_blockchain.py` | Monitoreo blockchain: wallets BTC/ETH con chequeo OFAC offline + online. |
| `finint_darkweb.py` | Análisis de texto FININT + scraping paste sites + detección de patrones sospechosos. |
| `finint_entity_linker.py` | Link de wallets y direcciones .onion → entity registry + cross-check OFAC. |
| `humint_bot.py` | Bot Telegram para reportes de campo HUMINT con fotos geolocalizadas y extracción EXIF. |
| `cctv_snapshot_collector.py` | Snapshot collector async para cámaras CCTV públicas con rotación FIFO y almacenamiento en disco. |

### Sistema de Agentes IA

| Agente | Perspectiva | Color |
|---|---|---|
| 🟢 **ARES** | Analista fáctico neutral (OSINT) | `#00ffaa` |
| 🔵 **MINERVA** | Perspectiva crítica / oposición | `#44aaee` |
| 🔴 **NEXUS** | Defensa soberana / oficialismo | `#ff4444` |
| ⚪ **COORD** | Coordinador del debate y síntesis final | — |

---

## 🚀 Inicio Rápido

### Requisitos Previos
- **Python 3.11+**
- **Google Chrome** (para módulos Playwright de scraping avanzado)

### En Windows
```bat
REM Opción 1 — Doble clic en:
start_cobalto.bat

REM Opción 2 — Con modo desarrollo (auto-reload):
start_cobalto.bat --dev
```

### En Linux / macOS
```bash
chmod +x start_cobalto.sh
./start_cobalto.sh

# Con modo desarrollo:
./start_cobalto.sh --dev
```

Accede a: **`http://127.0.0.1:8083`**

### Iniciar solo el Worker de Extracción
```bash
# Ciclo completo continuo:
python cobalto_worker.py

# Un solo ciclo (diagnóstico / CI):
python cobalto_worker.py --once
```

### Iniciar el Bot Telegram C4I
```bash
python telegrambot.py
```

---

## ⚙️ Configuración (`.env`)

Copia `.env.example` a `.env` y configura:

```env
# Credenciales de Administración
ADMIN_USERNAME=admin
ADMIN_PASSWORD=tu_contraseña_segura

# NVIDIA API (IA multiagente — mínimo 1 clave)
GROQ_API_KEY=nvapi-...
GROQ_API_KEY_ARES=nvapi-...
GROQ_API_KEY_MINERVA=nvapi-...
GROQ_API_KEY_NEXUS=nvapi-...

# Google Gemini (fallback IA)
GEMINI_API_KEY=AIza...

# Bases de datos opcionales
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/cobalto
REDIS_URL=redis://localhost:6379/0

# IA Local (LM Studio / llama.cpp)
LOCAL_AI_ENABLED=false
LOCAL_AI_ENDPOINT=http://127.0.0.1:1234/v1
LOCAL_AI_MODEL=local-model

# OSINT APIs externas (opcionales)
GITHUB_TOKEN=ghp_...
FIRMS_API_KEY=...
OPENWEATHER_API_KEY=...
SHODAN_API_KEY=...                # OSIRIS RECON: Shodan + InternetDB + CVE
TELEGRAM_TOKEN=...                # Token del bot C4I
TELEGRAM_CHANNEL=@canal           # Canal para broadcast RSS
```

---

## 📦 Instalación de Dependencias

```bash
# Instalar dependencias declaradas en pyproject.toml
pip install -e .

# O desde requirements.txt (alternativo, fijado por versión):
pip install -r requirements.txt

# Instalar navegadores para Playwright (scraping avanzado):
playwright install chromium
```

---

## 🗂️ Estructura del Proyecto

```
COBALTO/
├── app.py                        # Servidor FastAPI (entrada principal)
├── cobalto_worker.py             # Worker de extracción OSINT
├── ai_core.py                    # Motor de IA multiagente (debate)
├── ai_local.py                   # Fallback LLM local (LM Studio/llama.cpp)
├── config.py                     # Configuración centralizada
├── config_dynamic.json           # ⚙️ Persistencia del panel de configuración
├── database.py                   # Persistencia políglota SQLite/PostgreSQL + card_notes
│
├── extractor.py                  # Extractor RSS + Telegram público + circuit breaker
├── social_hub.py                 # Orquestador social unificado
├── social_public_extractor.py    # Extractor HTTP público
│
├── app_background.py             # Watchers de caché (File / Redis PubSub)
├── app_auth.py                   # Autenticación JWT
├── app_ws.py                     # WebSocket broadcast
├── app_platform.py               # Rutas de la plataforma
│
├── models/                       # 🛡️ Modelos Pydantic v2 de validación
│   └── intel_models.py           # Esquemas para static_intel.json (OwnPost, NotaInformativa)
│
├── routers/                      # 🧩 Sub-routers temáticos extraídos de app.py
│   ├── rt_humint.py              # Endpoints reportes HUMINT y bot Telegram (/api/humint/*)
│   ├── rt_finint.py              # Endpoints FININT blockchain, wallets y darkweb (/api/finint/*)
│   ├── rt_entities.py            # Endpoints búsqueda y stats entity registry (/api/entities/*)
│   ├── rt_predictive.py          # Endpoints alerta temprana y scoring (/api/predictive/*)
│   ├── rt_agents.py              # Endpoints orquestación agentes IA (/api/agent/*)
│   ├── rt_analytics.py           # Endpoints telemetría y métricas (/api/analytics-data, /cyber)
│   └── rt_export.py              # Endpoints exportación SitRep/OSINT DOCX/PDF/JSON (/api/export/*)
│
├── dashboard.py                  # Pipeline del dashboard (full cycle)
├── dashboard_pipeline.py         # Pipeline modular de datos
├── dashboard_sensors.py          # Sensores de telemetría en tiempo real
├── dashboard_heavy.py            # Ciclo pesado (análisis profundo)
│
├── correlation_engine.py         # Correlación geoespacial Haversine
├── telegrambot.py                # Bot Telegram C4I + RSS broadcast
├── user_search.py                # Búsqueda multi-plataforma + monitor de cambios en targets
├── export_sitrep_docx.py         # Exportación SitRep a Word (docxtpl)
├── export_sitrep_ia.py           # Análisis IA NVIDIA por entrada OSINT
├── export_sitrep_pdf.py          # Exportación SitRep a PDF (fpdf2)
├── historical_store.py           # Almacén histórico SQLite con partición mensual (90 días)
├── event_bus.py                  # Bus de eventos interno pub/sub (sin Redis)
├── entity_resolver.py            # Motor fuzzy matching (Levenshtein + token-set)
├── entity_registry.py            # Registro canónico de entidades SQLite
├── entity_linker.py              # Cross-source entity linker (social ↔ OFAC ↔ Wikidata)
├── agent_tools.py                # 9 tools envueltas para agentes + rate limiting
├── ares_investigator.py          # Detective autónomo de anomalías
├── agent_orchestrator.py         # Cola de tareas y scheduling de agentes
├── agent_memory.py               # Sesiones persistentes SQLite
├── predictive_scorer.py          # Motor de scoring probabilístico (5 señales)
├── early_warning.py              # 10 reglas de escalado + EarlyWarningEngine
├── finint_blockchain.py          # Monitoreo blockchain + OFAC wallet check
├── finint_darkweb.py             # Dark web intelligence + análisis de texto
├── finint_entity_linker.py       # Link wallets/onion → entity registry
├── backfill_entities.py          # One-shot poblador de entity registry
├── humint_bot.py                 # HUMINT field reports via Telegram + SQLite store
├── cctv_snapshot_collector.py    # Snapshot collector async para CCTV públicas
│
├── osint_*.py                    # Módulos OSINT especializados (15+)
├── osiris_bridge.py              # OSIRIS Engine — router FastAPI 33 endpoints
├── osiris_recon.py               # OSIRIS RECON toolkit (16 herramientas)
├── osiris_intel.py               # OSIRIS Intel — OFAC SDN + Wikidata SPARQL
├── flight_tracker.py             # Rastreo de aeronaves (ADS-B)
├── vessel_tracker.py             # Rastreo de buques (AIS)
├── event_radar.py                # Radar de eventos y alertas
│
├── sentiment_ml.py               # Motor NLP de análisis de sentimiento
├── sentiment_history.py          # Historial de ciclos de sentimiento
│
├── data/
│   ├── profile_snapshots.json    # Snapshots de perfiles para detección de cambios
│   └── historical/               # Cachés históricos para timeline scrubber
│
├── templates/
│   ├── index.html                # Orquestador Jinja2 (19 includes)
│   ├── avalanche.html            # Consola Avalanche (bridge externo)
│   └── partials/
│       ├── _head.html            # Meta, CSS, scripts CDN, CSP
│       ├── _sidebar.html         # Navegación lateral + selector de tema
│       ├── _tab_news.html        # Monitor Global (SitRep)
│       ├── _tab_intel.html       # Debate Multi-Agente IA
│       ├── _tab_social.html      # Monitor de Redes Sociales
│       ├── _tab_analytics.html   # Telemetría + Health Dashboard de Fuentes
│       ├── _tab_timeline.html    # Timeline con scrubber histórico
│       ├── _tab_actors.html      # Perfilamiento con monitor de cambios
│       ├── _tab_map.html         # Mapa unificado Leaflet — 7 capas OSIRIS + COBALTO
│       ├── _tab_osiris_recon.html # OSIRIS RECON Toolkit — 16 herramientas
│       ├── _tab_osiris_global.html # OSIRIS Live Feeds — CCTV + SIGINT + Aerospace
│       ├── _tab_config.html      # Panel de Configuración (+ subtab OSIRIS Engine)
│       └── ...                   # (15 tabs total)
│
├── static/
│   ├── css/dashboard.css         # Sistema de diseño + AMOLED/AMOLED+/Light
│   └── js/
│       ├── main.js               # Núcleo del dashboard — switchTab, preload, init
│       ├── map-unified.js        # Mapa Leaflet unificado — 7 capas OSIRIS + COBALTO con clustering
│       ├── osiris-recon.js       # UI del RECON toolkit (16 herramientas, tab dedicado)
│       ├── osiris-global.js      # CCTV viewer + SIGINT feed + Aerospace (tab Live Feeds)
│       ├── config_manager.js     # Panel de configuración UI (8 subtabs, 50+ parámetros)
│       ├── notes-system.js       # Anotaciones colaborativas en cards
│       ├── intel-core.js         # Motor de inteligencia procesada
│       ├── intel-analytics.js    # Analítica de red
│       ├── intel-graph.js        # Grafo SNA (vis-network / force-graph)
│       ├── sentiment-analysis.js # UI de análisis de sentimiento
│       ├── map_manager.js        # Mapa Leaflet legacy (pendiente de limpiar)
│       ├── chat_service.js       # Chat IA
│       ├── user_search.js        # Perfilamiento de actores
│       ├── timeline-analysis.js  # Auditoría cronológica con scrubber
│       ├── neo4j-graph.js        # Visor Neo4j force-graph
│       ├── palantir-search.js    # Búsqueda estilo Palantir
│       ├── slash-commands.js     # Comandos slash para búsqueda paramétrica
│       └── tactical-controls.js  # Controles tácticos en caliente (sliders)
│
├── deprecated_social/            # Módulos archivados (referencia histórica)
├── tests/                        # Suite de tests (pytest)
├── pyproject.toml                # Configuración del proyecto (PEP 517)
├── requirements.txt              # Dependencias fijadas por versión
├── start_cobalto.bat             # Lanzador Windows
└── start_cobalto.sh              # Lanzador Linux/macOS
```

---

## ⚙️ Panel de Configuración (UI Completado)

El sistema incluye un panel de configuración visual accesible desde la interfaz web en el tab "Configuración" (icono ⚙️). Soporta **+70 parámetros organizados en 9 subtabs**, con persistencia bidireccional y sincronización en caliente con el worker.

### Subtabs del Panel

| Subtab | Parámetros editables |
|---|---|
| **📡 RSS & Telegram** | Fuentes RSS (add/delete), fuentes Telegram público (add/delete), feeds prioritarios (add/delete) |
| **🎯 Keywords & Targets** | Keywords de búsqueda (add/delete), usuarios target (add/delete) |
| **🔌 Conectividad** | `CACHE_MAX_AGE_MINUTES`, `ENTRY_MAX_AGE_HOURS`, `CYCLE_INTERVAL_MINUTES`, `SSL_VERIFY`, `RESIDENTIAL_PROXY_URL`, `USE_TOR_FALLBACK`, `TOR_SOCKS_PORT`, `DEFCON_LEVEL`, `DATA_RETENTION_DAYS` |
| **⚙️ IA & LLMs** | `AI_TEMPERATURE`, `AI_MAX_TOKENS`, `LOGIC_ENGINE`, `CROSS_ANALYSIS_CONCURRENCY`, `LOCAL_AI_ENABLED`/`LOCAL_AI_ENDPOINT`/`LOCAL_AI_MODEL`, más 10 ajustes de prompts |
| **🧠 Sentimiento** | 6 léxicos emocionales (JSON arrays), 5 umbrales de alerta y muestreo |
| **🎛️ C4I** | Branding, módulos OSINT toggle, monitoreo sísmico (geocerca), alertas GDACS (radio/días), apagones ASN (threshold), **Diagnóstico Motor IA (Groq)**, y **Salud de Fuentes RSS** |
| **🔑 Tokens (.env)** | API keys de NVIDIA (Groq variables), Gemini, Telegram, OSINT externas (`SHODAN_API_KEY` incluida) |
| **🛩️ Rastreo Assets** | Tablas editables para aeronaves (ICAO) y buques (MMSI) |
| **🛰️ OSIRIS Engine** | Toggles de módulos (RECON/Intel/Map/CCTV/Feed), intervalos de polling del tab Global (6 params), intervalos por capa del mapa OSIRIS (6 params), y refresco de caché de sanciones OFAC SDN |

### Flujo de Configuración

```
Frontend (config_manager.js)          Backend (app.py)              Persistencia
┌─────────────────────┐    POST     ┌────────────────┐   save    ┌──────────────────┐
│   populateFields()  │ ◄── GET ── │  /api/config   │ ◄─────────│ config_dynamic   │
│   saveConfig()      │ ──── POST ──│  + validación  │ ────────► │ .json            │
│   saveEnvConfig()   │ ──── POST ──│  /api/env      │ ────────► │ .env             │
└─────────────────────┘            └────────────────┘           └──────────────────┘
                                  PubSub ──► Redis ──► cobalto_worker (recarga en caliente)
```

---

## ⌨️ Slash Commands — Búsqueda Paramétrica

Sistema de comandos slash tipo Discord/Slack para ejecutar búsquedas y navegación desde la barra de búsqueda principal.

| Comando | Descripción |
|---|---|
| `/search <término>` | Búsqueda global en Elasticsearch |
| `/osint <username>` | OSINT completo en todas las plataformas |
| `/twitter <user>` | Busca perfil en X/Twitter |
| `/instagram <user>` | Busca perfil en Instagram |
| `/telegram <user>` | Busca perfil en Telegram |
| `/tiktok <user>` | Busca perfil en TikTok |
| `/news <keyword>` | Filtra noticias por palabra clave |
| `/sentiment <term>` | Navega al análisis de sentimiento |
| `/tab <name>` | Cambia al tab especificado |
| `/help` | Muestra todos los comandos disponibles |
| `/clear` | Limpia filtros y resultados |

---

## 🎛️ Controles Tácticos en Caliente

Panel flotante de sliders paramétricos que actualizan la configuración en caliente vía `POST /api/config` → Redis PubSub → Worker.

| Control | Parámetro | Rango |
|---|---|---|
| Radio Sísmico | `SEISMIC_MAX_DISTANCE_KM` | 50–2000 km |
| Magnitud Mínima | `SEISMIC_MIN_MAGNITUDE` | 0.5–9.5 Mw |
| Caída de Red | `ASN_DROP_THRESHOLD` | 5–100% |
| Radio Desastres | `GDACS_MAX_DISTANCE_KM` | 50–5000 km |
| Cache OSINT | `CACHE_MAX_AGE_MINUTES` | 1–120 min |

---

## 🚨 Alertas Visuales de Apagón de Red

Las tarjetas de `network_outage` en el tab de Tiempo Real reciben tratamiento visual prioritario con animación `tactical-pulse-critical`, telemetry box y auto-silence a los 45s.

---

## 🔊 Alertas Sonoras Tácticas

Notificación auditiva vía Web Audio API cuando el WebSocket entrega eventos con alertas:

| Tipo | Frecuencia | Forma de Onda | Duración |
|---|---|---|---|
| `warning` (alertas > 0) | 880 Hz | Sawtooth | 0.5s |
| `critical` | 660 Hz | Square | 0.8s |
| `info` (ciclo completado) | 523 Hz | Sine | 0.15s |

- **Mute toggle**: botón 🔊/🔇 en la topbar, persiste en `localStorage`

---

## 📡 Health Dashboard de Fuentes

Tabla en el tab Analytics que muestra el estado de todas las fuentes OSINT con circuit breaker:

- 🟢 **Saludables** — sin fallos registrados
- 🟡 **Degradadas** — 1–2 fallos consecutivos
- 🔴 **Caídas** — 3+ fallos, en espera de reintento (10 min)

Actualización automática al cambiar al tab Analytics + botón manual 🔄.

---

## 👤 Monitor de Cambios en Targets

Sistema de snapshots de perfiles para detección de cambios en usuarios influyentes:

- **Snapshots** almacenados en `data/profile_snapshots.json`
- **Detección**: cambios en `display_name`, `bio` o `followers` (>10%)
- **Alertas**: tipo `profile_change` en el sistema de alertas del dashboard
- **UI**: notificaciones ⚠️ en el tab de Perfilamiento de Actores
- **Integración**: se ejecuta durante el ciclo completo del dashboard + vía `/api/influential`

---

## 🛰️ OSIRIS Engine — Inteligencia Global

OSIRIS es un motor de inteligencia global absorbido completamente dentro de COBALTO, reescrito en Python/Vanilla JS nativo. Proporciona 33 endpoints REST y una interfaz dedicada con RECON toolkit, CCTV world map y feed SIGINT.

### 📡 Endpoints de la API OSIRIS

| Grupo | Endpoints | Descripción |
|---|---|---|
| **Recon** | `GET /api/osiris/recon/dns`, `/whois`, `/bgp`, `/cve`, `/shodan`, `/mac`, `/phone`, `/github`, `/leaks`, `/ip`, `/threats`, `/ssl`, `/headers`, `/certs`, `/ipsweep`, `/ipintel` | 16 herramientas de reconocimiento OSINT |
| **Data** | `GET /api/osiris/data/cctv` | Cámaras IP expuestas geo-localizadas |
| **Data** | `GET /api/osiris/data/sigint` | Feed de inteligencia de fuente abierta |
| **Intel** | `GET /api/osiris/intel/wikidata?q=` | Resolución de entidades vía Wikidata SPARQL |
| **Sanctions** | `GET /api/osiris/sanctions/search?q=` | Búsqueda OFAC SDN (OpenSanctions) |
| **Sanctions** | `GET /api/osiris/sanctions/check?name=&country=` | Verificación de individuo/entidad contra SDN |
| **Sanctions** | `GET /api/osiris/sanctions/refresh` | Refresca caché local de sanciones |
| **Health** | `GET /api/osiris/health` | Estado de todos los módulos OSIRIS |
| **Entities** | `GET /api/entities/search?q=&type=&source=&ofac_only=` | Búsqueda en registro canónico de entidades |
| **Entities** | `GET /api/entities/{id}` | Detalle de entidad por ID |
| **Entities** | `GET /api/entities/stats` | Estadísticas del registro de entidades |
| **Historical** | `GET /api/historical/range?from=&to=&source=&category=&severity=&search=` | Consulta temporal en almacén histórico SQLite |
| **Historical** | `GET /api/historical/stats` | Estadísticas del almacén histórico |
| **Snapshots** | `GET /api/osiris/snapshots?camera_id=&limit=` | Lista de snapshots CCTV capturados |
| **Snapshots** | `GET /api/osiris/snapshots/stats` | Estadísticas del snapshot collector |

### 🧰 RECON Toolkit (16 Herramientas)

| Tool | Descripción | Fuente |
|---|---|---|
| DNS Lookup | Resolución A/AAAA/MX/NS/TXT/CNAME/SOA | dns.google / cloudflare-dns |
| WHOIS | Información de registro de dominio | whois |
| BGP Lookup | Prefijos ASN, IP range, origen | BGPView / RIPEstat |
| CVE Search | Vulnerabilidades por keyword/CVE ID | NVD NIST |
| Shodan Intel | Puertos, banners, servicios en IP | Shodah / InternetDB |
| MAC Lookup | Fabricante por OUI | MAC Address.io |
| Phone Lookup | Código de país, operador, tipo | Google LibPhoneNumber |
| GitHub Recon | Repos, emails, tokens expuestos | GitHub API |
| Leak Check | Filtraciones asociadas a email | LeakCheck / Snusbase |
| IP Geolocation | ISP, org, ubicación, VPN/proxy | ip-api.com |
| Threat Intel | Reputación, reports, malware | AlienVault OTX |
| SSL Checker | Certificado TLS/SSL, cadena, fechas | OpenSSL (socket) |
| HTTP Headers | Security headers analysis | aiohttp |
| Certificate Transparency | Certificados emitidos para dominio | crt.sh |
| Network Sweep | Barrido de puertos comunes en IP | asyncio socket |
| IP Intelligence | Score, ASN, pais, riesgo | Abstract API / ipapi |

### 🎛️ Interfaz OSIRIS

La interfaz OSIRIS se distribuye en **3 tabs** para evitar sobrecarga visual:

#### 🔍 OSIRIS RECON Toolkit (tab dedicado)
Tab full-page con 16 herramientas OSINT. Ahora con diseño **Split-Panel**: Sidebar a la izquierda categorizando herramientas por dominio, red, amenaza e identidad; área principal de resultados a la derecha. Incluye barra de búsqueda dinámica, historial de ejecuciones persistente, y exportación rápida de resultados a JSON. Interfaces limpias tipo tarjetas (glassmorphism) e interactividad optimizada.

#### 📡 OSIRIS Live Feeds
Tab con 2 columnas:
- **CCTV Network**: Mosaico de cámaras IP expuestas (TfL London, WSDOT Washington, Singapore LTA) con manejo de errores por cámara, polling automático y conteo en vivo.
  - **Grid Layout Toggle**: Botones 1×1, 2×2, 3×3, 4×4 para cambiar la densidad del mosaico en caliente.
  - **Doble Click → Expand**: Modal a pantalla completa con la imagen de la cámara, nombre y metadatos.
  - **Metadata Panel**: Al hacer clic en una cámara se muestra panel lateral con source, ciudad, país, lat/lng, tipo de stream y feed URL.
- **Aerospace & Satellites**: Conteo de satélites por categoría (Starlink, GPS, GEO, Science) y telemetría de vuelos militares (ADS-B) con callsign y velocidad.
- **SIGINT Feed**: Timeline de eventos de inteligencia de fuente abierta con severidad codificada por color (CRITICAL/HIGH/ELEVATED/LOW).

#### 🗺️ Mapa Unificado (Leaflet + OSIRIS + COBALTO)
El tab de mapa geoespacial usa **Leaflet** con **7 capas integradas** con clustering:
- **COBALTO Intel Points** (📌): Puntos geo-referenciados del pipeline (`/api/map-data`)
- **Military Flights** (🛩️): Vuelos militares ADS-B desde `/api/osiris/data/flights`
- **Satellites** (🛰️): Satélites visibles desde `/api/osiris/data/satellites`
- **Earthquakes** (🌋): Sismos recientes USGS con radio escalado por magnitud
- **Active Fires** (🔥): Incendios activos VIIRS desde `/api/osiris/data/fires`
- **Severe Weather** (🌪️): Eventos climáticos severos desde `/api/osiris/data/weather`
- **CCTV Cameras** (📹): Cámaras IP expuestas desde `/api/osiris/data/cctv`. Fuentes: TfL London, WSDOT Washington, Singapore LTA, **OpenStreetMap Venezuela**, **Insecam Venezuela**.
- Capa COBALTO desde `/api/map-data` + `window._initialMapData` (precargado)
- Layer Panel flotante con checkboxes, refresh individual y auto-polling
- Popups tácticos con datos formateados por tipo (callsign, magnitud, lugar, feed_url)
- Basemap CartoDB Dark con clustering por capa (`L.markerClusterGroup`)

### 🔐 Caché de Sanciones OFAC SDN

- Fuente: OpenSanctions CSV (`sanctions.csv`).
- Caché local: `data/osiris_sanctions_cache.json` con TTL de 24h.
- Actualización manual vía `GET /api/osiris/sanctions/refresh`.
- Búsqueda por nombre, país, tipo de entidad.

---

El bot de Telegram (`python telegrambot.py`) combina broadcast RSS con comandos interactivos:

| Comando | Descripción | Fuente de datos |
|---|---|---|
| `/start` | Bienvenida y lista de comandos | — |
| `/status` | Estado del sistema, entradas, alertas, circuit breakers | Caché persistente |
| `/alerts` | Últimas 10 alertas tácticas con severidad | Caché persistente |
| `/search <usuario>` | OSINT multi-plataforma | `user_search.py` |
| `/outages` | Apagones de red activos | Caché persistente |
| `/briefing` | Resumen ejecutivo IA | Caché persistente |
| `/help` | Ayuda de comandos | — |

---

## 🌍 Correlación Geoespacial

El motor `correlation_engine.py` cruza eventos de 4 fuentes mediante **Haversine**:

| Fuente | Tipo de evento | Geolocalización |
|---|---|---|
| `seismic_monitor` | Sismos USGS | Lat/Lng precisas |
| `gdacs_monitor` | Alertas GDACS (ciclones, incendios, volcanes) | Lat/Lng (centroide) |
| `asn_monitor` | Apagones de red | Centro de Venezuela (estimado) |
| `events_tracker` | Incidentes de seguridad, protestas | Lat/Lng cuando disponible |

**Umbrales**: radio 300 km, ventana temporal 24h.  
**Output**: `composite_events` inyectados como alertas en el dashboard con centroide, distancia y delta temporal.

---

## ⏱️ Reproductor de Línea de Tiempo

Slider interactivo en el tab Timeline que permite navegar el estado histórico:

- **Rango**: 7 días (168h) con resolución de 1h
- **Endpoint**: `GET /api/historical?timestamp=T&hours=N`
- **Feedback**: contador de entradas en esa ventana temporal
- **Modos**: 🔴 EN VIVO (default) ↔ ⏪ HISTÓRICO (al desplazar el slider)

---

## 📝 Anotaciones Colaborativas

Sistema de notas operativas persistentes sobre cualquier card del dashboard:

- **Activación**: doble clic sobre cualquier card (`.news-card`, `.rt-card`, `.panel-glass`, etc.)
- **Persistencia**: SQLite (`card_notes` table) con `card_id`, `card_type`, `note`, `author`, `updated_at`
- **Badge**: 📝 en cards que ya tienen notas guardadas
- **Auto-save**: 500ms de debounce al escribir
- **API**: `GET /api/notes[?card_id=]`, `POST /api/notes`

---

## 🎨 Temas Visuales

| Tema | Clase CSS | Fondo | Acento | Cuándo usarlo |
|---|---|---|---|---|
| **Cyber** (default) | — | `#0A0B10` | `#00E5FF` | Uso diario, alto contraste |
| **AMOLED** | `.theme-amoled` | `#000000` | `#38BDF8` | Pantallas OLED, mínimo consumo |
| **AMOLED+** | `.theme-amoled-plus` | `#000000` | `#3291FF` | Negro puro, acentos desaturados, sin glass blur |
| **Light** | `.theme-light` | `#FFFFFF` | `#0284C7` | Entornos iluminados, impresión |

**Selector rápido** en el footer del sidebar (🌙 ⬛ 🔵 ☀️). Persiste en `localStorage`.

---

## 🛡️ Modos de Persistencia

| Backend | Variable | Estado |
|---|---|---|
| **SQLite** (default) | — | ✅ Sin configuración |
| **PostgreSQL** | `DATABASE_URL=postgresql+asyncpg://...` | Activado automáticamente |
| **Redis** (caché + PubSub) | `REDIS_URL=redis://...` | Activado automáticamente |
| **Elasticsearch** | `ELASTICSEARCH_URL=http://...` | Módulo `osint_elasticsearch.py` |
| **Neo4j** (grafo) | `NEO4J_URI=bolt://...` | Módulo `osint_neo4j.py` |

---

## 📊 Ciclos de Extracción

| Ciclo | Frecuencia | Qué hace |
|---|---|---|
| **Fast Track** | ~15 min | RSS prioritarios + Telegram público |
| **Full Track** | ~30 min | Todos los feeds + Redes sociales |
| **Heavy Track** | ~60 min | Análisis IA profundo + grafos + ciberseguridad |

---

## 🔒 Seguridad

- Autenticación JWT con rotación de tokens.
- Contraseñas hasheadas con **PBKDF2-HMAC-SHA256 + salt** (100k iteraciones).
- CSP (Content Security Policy) en todas las páginas.
- Escudo **DoH (DNS over HTTPS)** integrado para evadir censura regional.
- Verificación de certificados SSL configurable por feed.
- **Validación backend**: todos los parámetros de configuración validados con rangos (HTTP 400 + mensaje descriptivo).
- **API keys aisladas**: tokens sensibles solo en `.env`, nunca en `config_dynamic.json`.

---

## 📝 Mantenimiento y Logs

Los logs rotan automáticamente al alcanzar **5 MB** (máximo 3 copias):

| Archivo | Proceso | Tamaño máx. |
|---|---|---|
| `worker.log` | `cobalto_worker.py` | 15 MB (5 MB × 3) |
| `extractor.log.txt` | `extractor.py` | 10 MB (5 MB × 2) |
| `server.log` | `app.py` | 15 MB (5 MB × 3) |

**Mantenimiento de base de datos:** Al arrancar `app.py`, se ejecuta automáticamente:
- Purga de `sent_news` > 3 días.
- Purga de `social_graph_cache.db` > 7 días + `VACUUM`.

---

## 🧪 Tests

```bash
# Ejecutar suite completa (127 tests):
python -m pytest tests/ -v

# Verificar modelos de inteligencia Pydantic:
python -m pytest tests/test_intel_models.py

# Verificar endpoints HTTP e integración de routers:
python -m pytest tests/test_api_endpoints.py

# Verificar seguridad:
python -m pytest tests/test_security.py
```

---

## 📱 PWA (Progressive Web App)

Cobalto Hub es instalable como aplicación de escritorio:
1. Inicia el servidor.
2. En Chrome/Edge, haz clic en el ícono de instalación (⊕) en la barra de direcciones.
3. El dashboard funcionará como app nativa con acceso offline parcial.

---

## 🗺️ Historial de Versiones

| Versión | Fecha | Cambios clave |
|---|---|---|
| **v14.3** | 2026-08-24 | **Migración Social Nitter → Bluesky + Mastodon & Estabilización Launcher**: Eliminación completa de Nitter (discontinuado desde 2024). `social_hub.py` reemplaza `fetch_nitter()` por `fetch_bluesky()` (AT Protocol, sin auth) y `fetch_mastodon()` (REST API, 3 instancias fallback). 4 nuevas fuentes de datos sociales en tiempo real: `#venezuela` y `#ciberseguridad` en ambas plataformas. Timeout del launcher desktop ampliado de 15s a 45s. Logs sociales degradados a WARNING. |
| **v14.2** | 2026-08-24 | **Marco DGAE Colombia 2026 & Hardening**: Integración completa del set de inteligencia DGAE 2026 para Colombia (164+ keywords, 26 targets de alto perfil, 5 fuentes RSS estratégicas: *Colombia+20*, *InSight Crime*, *Infobae*, *Indepaz*, *FIP*). Parcheo dinámico de fuentes caídas (`feed_patches.json`), aceleración del rate-limiter de redes sociales, circuit breakers optimizados en OSINT tiempo real y bypass SSL en scraping BCV. |
| **v13.0** | 2026-08-20 | **Arquitectura Multipaís (Multi-Theater OSINT)**: Escalado del sistema a un motor multi-teatro modular mediante perfiles JSON (`data/theaters/`), registro `theaters_config.py`, auto-etiquetado de noticias (`country_tags`), selector de teatro en la barra lateral con navegación suave (`flyTo`) en el mapa Leaflet, endpoint `GET /api/theaters` y geocercas sísmicas multipaís. 132/132 tests aprobados. |
| **v12.6** | 2026-08-19 | **Arquitectura Nativa PyQt6 & Bandeja de Sistema**: Migración a `PyQt6/QWebEngineView` en `cobalto_desktop.py` con System Tray icon, Windows Mutex monoinstancia, WebSocket continuous rehydration en `main.js`, retención TTL de noticias en config UI y compilación PyInstaller `build_exe.py`. |
| **v12.5** | 2026-08-19 | **Blue Force Tracking (BFT)**: Monitoreo de operadores en terreno con ingesta de telemetría en tiempo real (`/api/telemetry/heartbeat`), almacenamiento en `operator_registry` y `operator_telemetry`, métricas de fuerza táctica (activos, sin señal, SOS), rastro histórico GPS (breadcrumbs), nivel de batería con código de color y tipo de red (`4G`/`Wi-Fi`/`AEGIS Mesh`). 8va capa de operadores en el Mapa Unificado Leaflet (`map-unified.js`), pestaña táctica dedicada `_tab_operators.html` + `operators-manager.js`, integración de alertas de Hombre Muerto y Pánico Manual SOS con aviso sonoro y visual prioritario en el HUB. Suite de 132 tests pasando al 100%. |
| **v12.0** | 2026-07-21 | **CCTV Snapshot Collector**: `cctv_snapshot_collector.py` — módulo async con aiohttp para capturar frames JPEG de todas las cámaras CCTV públicas (TfL, WSDOT, Singapore, OSM Venezuela, Insecam Venezuela). Rotación FIFO (100 snaps/cámara), almacenamiento en `data/cctv_snapshots/`, persistencia en `historical_store` con `category="cctv_snapshot"`. Se ejecuta automáticamente en el ciclo Heavy del worker. Endpoints `GET /api/osiris/snapshots` y `/api/osiris/snapshots/stats`. **Cámaras Venezuela**: 2 nuevas fuentes en `/api/osiris/data/cctv` — OpenStreetMap Overpass API (webcams voluntarias) e Insecam (cámaras IP públicas). **Fix tabs vacíos**: Entity Explorer, Agent Feed, Predictive Alerts, FININT y HUMINT ahora tienen botones de acción para poblar datos (backfill, ejecutar ciclo, crear reporte de ejemplo) y están correctamente inicializados desde switchTab. **FASE 5 — HUMINT & Edge Computing**: `humint_bot.py` recepción de reportes de campo vía Telegram con fotos geolocalizadas, extracción de coordenadas desde EXIF/caption, análisis de severidad por texto, almacenamiento SQLite persistente, 5 endpoints REST (`/api/humint/reports`, `/api/humint/report/{id}`, `/api/humint/report` POST, `/api/humint/report/{id}/status`, `/api/humint/stats`), frontend `_tab_humint.html` + `humint.js` con formulario de reporte, filtros por estado, timeline de reportes, sidebar badge 🕵️. Air-gapped compatible vía `ai_local.py` y `LOCAL_AI_ENABLED`. Tests: 9 tests HUMINT. **FASE 4 — FININT & Dark Web**: `finint_blockchain.py` monitoreo de wallets BTC/ETH con chequeo OFAC offline + online. `finint_darkweb.py` scraping paste sites + análisis texto con patrones sospechosos. `finint_entity_linker.py` registro wallets/onion → entity registry. Frontend 4 sub-tabs. Tests: 9 tests. **FASE 3 — Alerta Temprana Predictiva**: `predictive_scorer.py` scoring 5 señales, `early_warning.py` 10 reglas de escalado. Frontend + badge sidebar. **FASE 2 — Flujos Agénticos IA**: `agent_tools.py` (9 tools), `ares_investigator.py`, `agent_orchestrator.py`, `agent_memory.py`. Frontend Agent Feed. **FASE 1 — Knowledge Graph**: `entity_resolver.py`, `entity_registry.py`, `entity_linker.py`. Entity Explorer + OFAC/Wikidata badges. **FASE 0 — Infraestructura Base**: `historical_store.py`, `event_bus.py` (+ Redis bridge), graph snapshots con entity_ids. **Deuda Técnica**: 72 tests unitarios total, `backfill_entities.py`, Redis PubSub bridge. |
| **v11.3** | 2026-07-21 | **Migración de IA a NVIDIA NIM API**: Se sustituyó el proveedor Groq por la API de NVIDIA integrando los modelos `deepseek-v4-flash` y `gemma-4-31b-it`. La arquitectura ahora utiliza el cliente `openai` apuntando a `integrate.api.nvidia.com`, superando límites previos de tokens. **OSIRIS RECON UI V2**: Rediseño del RECON Toolkit a un modelo *Split-Panel*, categorización jerárquica de 16 módulos, retención de historial, placeholders inteligentes y exportación nativa a JSON. |
| **v11.2** | 2026-07-17 | **CCTV Viewer — UX Improvements**: Grid layout toggle (1×1, 2×2, 3×3, 4×4) para cambiar densidad del mosaico en caliente; doble clic en cámara expande modal a pantalla completa con imagen, nombre y metadatos; clic simple abre panel lateral de metadatos (source, ciudad, país, lat/lng, stream type, feed URL). Refactor completo de `osiris-global.js` con estado centralizado y nuevo módulo CSS en `dashboard.css`. |
| **v11.1** | 2026-07-17 | **Config Panel OSIRIS**: Nuevo subtab `🛰️ OSIRIS Engine` con 18 parámetros (5 toggles de módulos, 6 intervalos Global tab, 6 intervalos Map layers, 1 sanctions cache). **Backend**: variables persistidas en `config.py` via `load_dynamic_config/save_dynamic_config`, expuestas en `GET /api/config`. **Tokens**: `SHODAN_API_KEY` agregado al subtab Tokens + `.env`. Integración bidireccional completa UI ↔ backend. |
| **v11.0** | 2026-07-17 | **OSIRIS Engine — Absorción Completa**: 3 nuevos módulos backend (`osiris_bridge.py`, `osiris_recon.py`, `osiris_intel.py`) con 33 endpoints REST bajo `/api/osiris/*`; **RECON Toolkit**: 16 herramientas OSINT (DNS, WHOIS, BGP, CVE, Shodan, MAC, Phone, GitHub, Leaks, IP, Threats, SSL, Headers, Certs, IP Intel, Network Sweep) con UI nativa Vanilla JS; **OFAC SDN Sanctions**: caché local de OpenSanctions + Wikidata SPARQL resolver con búsqueda y verificación; **Tab 🛰️ OSIRIS Global Intel**: Interfaz táctica de 3 columnas con CCTV World Map, SIGINT Feed, Mercados y Crypto, Cyber Threats (CISA KEV + Malware), Tracker Aeroespacial (Satélites y Vuelos) y Alertas de Desastres (Clima Espacial, Sismos, Incendios); **Arquitectura**: repositorio `osiris-master` eliminado tras asimilar toda su funcionalidad al núcleo unificado de COBALTO. |
| **v10.1** | 2026-07-13 | **Dashboard Realtime**: rediseño táctico con tarjetas semánticas por categorías (Vuelos ADS-B, Buques AIS, Sismos USGS, Alertas ASN/GDACS, Open Data) y contadores KPI en vivo; **Diagnóstico IA (C4I)**: monitoreo en vivo del motor Groq, pool de claves, factor de estrés, circuit breaker y errores por API key; **Salud de Fuentes (C4I)**: tabla integrada para monitoreo de estado de fuentes RSS con refresh manual; **Sidebar Inteligente**: indicador de salud de IA con polling dinámico (operacional/degradada/caída). |
| **v10.0** | 2026-07-08 | **Export SitRep JSON**: endpoint `/api/export/sitrep` con estado completo del sistema, alertas, outages y briefing; **Alertas Sonoras**: Web Audio API con 3 perfiles (warning/critical/info) + mute toggle persistente; **Health Dashboard**: tabla de salud de fuentes OSINT con circuit breaker (verde/amarillo/rojo); **Monitor de Cambios en Targets**: snapshots de perfiles con detección de cambios en bio, nombre y followers, alertas `profile_change` en el pipeline; **Telegram Bot C4I**: 6 comandos interactivos (`/status`, `/alerts`, `/search`, `/outages`, `/briefing`, `/help`) con datos en vivo desde caché; **Correlación Geoespacial**: motor Haversine que cruza sismos, GDACS, apagones ASN y eventos de seguridad → `composite_events` en dashboard; **Timeline Scrubber**: slider histórico de 7 días con endpoint `/api/historical` y filtrado temporal de entradas; **Anotaciones Colaborativas**: doble clic en cualquier card abre textarea inline con persistencia SQLite y badge 📝; **Modo AMOLED+**: tema negro puro con acentos desaturados, sin glass blur; **Exportación DOCX + PDF + IA Pipeline**: 5 endpoints de exportación (`/docx`, `/pdf`, `/analizar`, `/generar-word`, `/generar-pdf`) con generación de documentos Word via docxtpl (Jinja2), PDF profesional via fpdf2, y análisis Groq por entrada (actores/amenaza/analísis) heredado de BOTDOCUMENTO; **Refactorización UI/UX completa**: sistema de componentes CSS (kpi-card, btn-export, source-health-table, empty-state, grid-2/3/4), jerarquía tipográfica (heading-1..4), skeleton loaders extendidos a timeline/analytics/user-search, tooltip en timeline scrubber, funciones de descarga unificadas, responsive mejorado, contraste modo Light optimizado |
| **v9.3** | 2026-07-08 | Slash Commands, Controles Tácticos, ASN Monitor mejorado, Alertas Visuales de Apagón, validación backend ampliada |
| **v9.2** | 2026-07-08 | Panel de Configuración completo, Monitor Sísmico USGS, Alertas GDACS, Emergencias Aéreas, Apagones de Internet |
| **v9.1** | 2026-07-07 | Modularización frontend (19 partials), consolidación social, rotación de logs, Pydantic v2 |
| **v9.0** | 2026-06 | Arquitectura worker/servidor separada, debate tripartito IA, políglota persistence |
| **v8.x** | 2025 | Dashboard monolítico, extracción en servidor |

---

---

## 🎨 Sistema de Diseño UI/UX

COBALTO implementa un sistema de diseño **ciberpunk-táctico** con glassmorphism, paleta de amenazas codificada por colores y jerarquía visual consistente en 13 pestañas.

### 🏗️ Jerarquía Tipográfica

| Clase | Tamaño | Uso |
|---|---|---|
| `.heading-1` | 1.8rem | Títulos de página (page-title) |
| `.heading-2` | 1.4rem | Títulos de tab (Monitor Global, Timeline) |
| `.heading-3` | 1.1rem | Títulos de panel (Salud de Fuentes, KPIs) |
| `.heading-4` | 0.95rem | Subtítulos de cards (Vectores de Amenaza) |

### 🎯 Clases de Componentes

| Clase | Propósito |
|---|---|
| `.kpi-card {.kpi-critical\|.kpi-warning\|.kpi-stable}` | Tarjeta KPI con borde izquierdo codificado por nivel de amenaza |
| `.btn-export {.btn-export-json\|.btn-export-docx\|.btn-export-ia}` | Botones de exportación con colores por tipo (púrpura/cian/verde) |
| `.source-health-table` | Tabla de salud de fuentes con estilo táctico |
| `.empty-state` | Estado vacío con icono, título y descripción |
| `.panel-tactical` | Panel con fondo oscuro y borde sutil |
| `.news-card` | Card principal de noticias con glassmorphism |
| `.skeleton-card` / `.skeleton-line` | Skeleton loaders con shimmer animation |
| `.grid-2` / `.grid-3` / `.grid-4` / `.analytics-grid` | Sistema de grillas responsive |
| `.flex` / `.flex-between` / `.flex-center` / `.flex-wrap` | Utilidades de layout |
| `.gap-05` / `.gap-1` / `.gap-15` / `.gap-2` | Espaciado consistente |
| `.font-mono` / `.text-muted` / `.text-primary` | Tipografía y color utilitarios |

### 🎭 Temas Visuales

| Tema | Clase CSS | Fondo | Acento | Característica |
|---|---|---|---|---|
| **Cyber** (default) | — | `#0A0B10` | `#00E5FF` | Uso diario, alto contraste, glassmorphism |
| **AMOLED** | `.theme-amoled` | `#000000` | `#38BDF8` | Pantallas OLED, mínimo consumo |
| **AMOLED+** | `.theme-amoled-plus` | `#000000` | `#3291FF` | Negro puro, sin glass blur, acentos desaturados |
| **Light** | `.theme-light` | `#FFFFFF` | `#0284C7` | Entornos iluminados, `--text-muted: #334155` |

**Selector rápido** en el footer del sidebar (🌙 ⬛ 🔵 ☀️). Persiste en `localStorage`.

### 🧩 Skeleton Loaders

El sistema inyecta skeletons shimmer en 7 tabs durante la carga asíncrona de datos:

| Tab | Tipo de Skeleton | Cobertura |
|---|---|---|
| tab-news | News cards (grid) | ✅ |
| tab-social | Social groups (stacked) | ✅ |
| tab-realtime | RT cards (grid) | ✅ |
| tab-narrative | Narrative groups (stacked) | ✅ |
| tab-cyber | Cyber cards (grid) | ✅ |
| **tab-timeline** | CIB + Alerts containers | ✅ *nuevo* |
| **tab-analytics** | KPI cards + Health table | ✅ *nuevo* |
| **tab-user-search** | Search result cards | ✅ *nuevo* |

Los skeletons se remueven automáticamente cuando los datos reales se renderizan.  
En modo `prefers-reduced-motion`, todas las animaciones se desactivan.

### 📱 Comportamiento Responsive

| Breakpoint | Cambios |
|---|---|
| ≤1200px | AI Panel → overlay lateral con FAB flotante, sidebar angosta |
| ≤768px | Sidebar → bottom nav bar con scroll-snap, KPIs → 1 columna, timeline scrubber con touch area extendida, botones export compactos |
| Print | Oculta paneles laterales, fondo blanco, textos negros |

### ⏱️ Timeline Scrubber

Slider interactivo que admite arrastre con tooltip de fecha:

- **Tooltip**: muestra la fecha exacta (`DD/MM/AAAA HH:MM`) al arrastrar el pulgar
- **Detección**: modo EN VIVO (🔴) cuando el slider está al final, HISTÓRICO (⏪) al retroceder
- **Estados vacíos**: containers CIB y Alertas muestran empty state con instrucciones
- **Rango**: 168 horas (7 días) con resolución de 1 hora
- **Endpoint**: `GET /api/historical?timestamp=T&hours=N`

### 📤 Sistema de Exportación Unificado

Tres formatos de exportación desde la topbar y el tab Analytics, implementados mediante una función genérica `window.downloadReport()`:

| Botón | Formato | Endpoint | Color |
|---|---|---|---|
| `⎙ JSON` | JSON estructurado | `GET /api/export/sitrep` | Púrpura `#B388FF` |
| `📄 DOCX` | Word con plantilla Jinja2/docxtpl | `GET /api/export/sitrep/docx` | Cian `#00E5FF` |
| `📕 PDF` | PDF profesional con fpdf2 | `GET /api/export/sitrep/pdf` | Rojo `#FF5050` |
| `🤖 IA+DOCX` | Análisis IA NVIDIA + Word | `POST /api/export/sitrep/generar-word` | Verde `#00FFAA` |
| `🤖 IA+PDF` | Análisis IA NVIDIA + PDF | `POST /api/export/sitrep/generar-pdf` | Rojo `#FF5050` |

### 🎨 Refactorización CSS

Estado actual de migración de estilos inline a clases CSS modulares:

| Área | Estado | Clases agregadas |
|---|---|---|
| Botones de exportación | ✅ Completado | `btn-export`, `btn-export-json/docx/ia` |
| Tarjetas KPI Analytics | ✅ Completado | `kpi-card`, `kpi-label`, `kpi-value`, `kpi-critical/warning/stable` |
| Tabla Health Sources | ✅ Completado | `source-health-table` |
| Timeline Scrubber | ✅ Completado | `#scrubber-tooltip`, empty-state |
| Grillas responsive | ✅ Completado | `grid-2/3/4`, `analytics-grid` |
| Skeleton loaders | ✅ Completado | Extendido a timeline/analytics/user-search |
| Variables de contraste Light | ✅ Completado | `--text-muted: #334155` |

---

## 🔭 Roadmap y Visión a Futuro (Norte del Proyecto)

COBALTO HUB evolucionará de ser una plataforma **Descriptiva/Analítica** a un ecosistema **Predictivo y Autónomo**, consolidando su capacidad como el "cerebro" de inteligencia C4I.

Todas las fases del roadmap original han sido completadas:

| Fase | Componente | Estado |
|---|---|---|
| **FASE 0** | Infraestructura Base — `historical_store.py`, `event_bus.py`, Redis PubSub | ✅ |
| **FASE 1** | Knowledge Graph — `entity_resolver.py`, `entity_registry.py`, `entity_linker.py` | ✅ |
| **FASE 2** | Flujos Agénticos IA — `agent_tools.py`, `ares_investigator.py`, `agent_orchestrator.py`, `agent_memory.py` | ✅ |
| **FASE 3** | Alerta Temprana Predictiva — `predictive_scorer.py`, `early_warning.py` | ✅ |
| **FASE 4** | FININT & Dark Web — `finint_blockchain.py`, `finint_darkweb.py`, `finint_entity_linker.py` | ✅ |
| **FASE 5** | HUMINT & Edge Computing — `humint_bot.py`, Air-Gapped Mode | ✅ |
| **Deuda Técnica** | Tests unitarios (63 total), `backfill_entities.py`, Redis PubSub bridge | ✅ |

### Próximas Direcciones

- **Investigación Autónoma:** Si el sistema detecta anomalías (ej. caída crítica de ASN + protesta), la IA utilizará automáticamente el OSIRIS RECON Toolkit para investigar la infraestructura y emitir un informe pre-empaquetado.
- **Monitoreo Dirigido Activo:** Asignación de "vigilancia" de entidades o hashtags a agentes específicos que reporten desvíos de comportamiento o anomalías sin interacción manual.
- **Predictive Policing:** "Apagón en Región X + Historial de manifestaciones = Alerta de probabilidad de disturbios al 85%".
- **Detección Temprana de Narrativas:** Predecir el surgimiento y viralidad de campañas de desinformación (Fake News) antes de que alcancen picos de interacción, basándose en la velocidad de propagación (velocity metrics).
- **Link-Analysis Visual:** Interfaces que permitan explorar y arrastrar nodos (entidades, billeteras cripto, servidores) para descubrir conexiones ocultas.
- **Pestaña de Debate Multiagente Completo (ARES · MINERVA · NEXUS):** Integración y ejecución continua de debates tripartitos multiagente en tiempo real, guardada para implementación futura cuando se escale la capacidad de cómputo/hardware local o clusters de inferencia dedicados.

---

*Sistema clasificado para uso interno. No redistribuir sin autorización.*
