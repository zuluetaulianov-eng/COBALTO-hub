# AGENTS.md — COBALTO HUB

Guía para asistentes IA que trabajan en este repositorio.

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Frontend | Vanilla JS (sin frameworks, sin bundlers) |
| Templates | Jinja2 (server-side rendering) |
| CSS | `dashboard.css` único (~2790 líneas) |
| Testing | pytest (asyncio_mode=auto) |
| Linter | Ruff (line-length=120) |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |

---

## Comandos

```bash
# Iniciar servidor web
python app.py

# Iniciar aplicación de escritorio nativa (Windows GUI)
python cobalto_desktop.py

# Compilar ejecutable nativo de Windows (.exe)
python build_exe.py

# Iniciar worker
python cobalto_worker.py

# Tests
python -m pytest tests/ -v

# Lint
ruff check .

# Type check
mypy --ignore-missing-imports --check-untyped-defs .

# Verificar sintaxis de un archivo específico
python -c "import ast; ast.parse(open('archivo.py', encoding='utf-8').read())"

# Verificar importaciones
python -c "import sys; sys.path.insert(0, '.'); from app import app"
```

---

## Estructura del Proyecto

### Backend (Python)
| Archivo | Propósito |
|---|---|
| `app.py` | Servidor FastAPI — rutas, WebSocket, config endpoints |
| `cobalto_desktop.py` | Lanzador de aplicación nativa de escritorio Windows (PyWebView) |
| `config.py` | Configuración centralizada + persistencia dinámica |
| `osiris_bridge.py` | Router OSIRIS 33 endpoints `/api/osiris/*` |
| `osiris_recon.py` | 16 herramientas RECON (DNS, WHOIS, BGP, CVE, etc.) |
| `osiris_intel.py` | OFAC SDN + Wikidata SPARQL resolver |
| `finint_blockchain.py` | Monitoreo blockchain (wallets BTC/ETH, chequeo OFAC offline + online) |
| `finint_darkweb.py` | Dark Web intelligence (paste sites, .onion scraping, análisis de texto FININT) |
| `finint_entity_linker.py` | Link wallets/onion addresses → entity registry + OFAC |
| `dashboard.py` | Pipeline de datos del dashboard |
| `ai_core.py` | Motor de debate multiagente IA |
| `extractor.py` | Extractor RSS + Telegram público |

### Frontend (Vanilla JS)
| Archivo | Propósito |
|---|---|
| `main.js` | Núcleo del dashboard — switchTab, preload, init (`CobaltoCore`) |
| `map-unified.js` | Mapa Leaflet unificado — 7 capas OSIRIS + COBALTO con clustering |
| `osiris-recon.js` | UI del RECON toolkit (16 herramientas, tab dedicado) |
| `osiris-global.js` | CCTV viewer — grid layout toggle (1×1–4×4), doble click → expand modal, metadata panel lateral, SIGINT feed + Aerospace |
| `config_manager.js` | Panel de configuración UI (incluye subtab OSIRIS Engine) |
| `map_manager.js` | Mapa Leaflet legacy (pendiente de limpiar) |
| `dashboard.css` | Único archivo CSS (~2790 líneas) |
| *Otros* | `intel-core.js`, `intel-graph.js`, `notes-system.js`, `chat_service.js`, `sentiment-analysis.js`, `user_search.js`, `palantir-search.js`, `slash-commands.js`, etc. |

### Templates
| Archivo | Propósito |
|---|---|
| `templates/index.html` | Orquestador Jinja2 — incluye todos los partials y scripts con `defer` |
| `templates/partials/_head.html` | Meta, CSS, scripts CDN (Leaflet, maplibre-gl, Chart.js, etc.), CSP |
| `templates/partials/_sidebar.html` | Navegación lateral con botones de tabs y selector de tema |
| `templates/partials/_tab_map.html` | Mapa unificado Leaflet (7 capas OSIRIS + COBALTO) + layer panel flotante |
| `templates/partials/_tab_osiris_recon.html` | RECON Toolkit full-page (16 herramientas OSINT) |
| `templates/partials/_tab_osiris_global.html` | Live Feeds: CCTV (grid toggle 1×1–4×4, expand modal, metadata panel) + SIGINT + Aerospace |
| `templates/partials/_tab_config.html` | Panel de Configuración (+ subtab `🛰️ OSIRIS Engine` con 18 parámetros) |
| `templates/partials/_tab_*.html` | ~15 partials de tabs (news, intel, social, analytics, timeline, actors, etc.) |

---

## Convenciones de Código

### Generales
- **NO** agregar comentarios en JS/CSS/Python a menos que sea código legacy confuso
- **NO** escribir nuevas dependencies sin antes verificar que no existan en `requirements.txt` / `pyproject.toml`
- **NO** crear archivos `.md` (documentación) a menos que el usuario lo pida explícitamente
- Variables, funciones y archivos en inglés (con nombres descriptivos)

### Python
- FastAPI + Pydantic v2 para validación
- `async def` para endpoints y operaciones I/O
- `aiohttp` para HTTP async (ya incluido)
- Todo nuevo módulo OSIRIS va en `osiris_bridge.py` + su propio `osiris_*.py`
- Variables de configuración OSIRIS se declaran en `config.py` con prefijo `OSIRIS_`
- Las rutas se registran en `app.py` vía `app.include_router()`
- Autenticación JWT vía middleware en `app_auth.py`

### Frontend (Vanilla JS)
- Sin frameworks, sin bundlers, sin npm
- Sin React, Vue, Svelte, etc.
- Los scripts se cargan con `defer` desde `index.html`
- Cada módulo expone un objeto global (`window.UnifiedMap`, `window.OsirisRecon`, `window.OsirisGlobal`, etc.)
- Naming: `window.NombreModulo = { state: {}, init: function() {...}, ... }`
- El DOM se manipula directamente (innerHTML, createElement, etc.)
- Eventos: `addEventListener`, no atributos `onclick` en HTML (excepto en partials)
- `switchTab()` en `main.js` orquesta la inicialización de cada módulo al cambiar de tab (ej: `UnifiedMap.init()` para tab-map)
- Estilo UI: ciberpunk-táctico (glassmorphism, #0A0B10 fondo, #00E5FF acento)

### CSS
- Un solo archivo: `static/css/dashboard.css`
- Variables CSS: `--bg-color`, `--primary: #00E5FF`, `--text-muted`, `--border-color`
- Temas: `cyber` (default), `theme-amoled`, `theme-amoled-plus`, `theme-light`
- Clases de componentes: `.panel-glass`, `.btn-tactical`, `.news-card`, `.config-chip`, `.cctv-card`, `.cctv-layout-btn`, `.cctv-meta-row`

### Jinja2
- Partial naming: `_tab_nombre.html` (underscore prefix para includes)
- Variables inyectadas desde `app.py`: `{{ ENTRY_MAX_AGE_HOURS }}`, `{{ all_entries }}`, etc.
- Datos precargados expuestos como `window._initial*` en `index.html`

---

## OSIRIS Engine — Reglas Específicas

### Backend
- Router registrado como `osiris_router` en `app.py` línea 27 y 188
- Todos los endpoints bajo `/api/osiris/*`
- Recon tools importadas desde `osiris_recon.py`, intel desde `osiris_intel.py`
- Rate limiting: 30 requests/60s por IP
- Sanctions cache: `data/osiris_sanctions_cache.json`, refresh cada `OSIRIS_SANCTIONS_REFRESH_HOURS`

### Mapa Unificado Leaflet
- Inicializado en `map-unified.js` como `window.UnifiedMap`
- 7 capas con clustering: cobato, flights, satellites, earthquakes, fires, weather, cctv
- Capa COBALTO desde `/api/map-data` + `window._initialMapData`
- Layer panel flotante en `_tab_map.html` con toggles y refresh individual

### Config Panel
- OSIRIS settings van en el subtab `subtab-osiris`
- SHODAN_API_KEY se configura en el subtab Tokens
- Las variables se persisten vía `POST /api/config` → `config.py:save_dynamic_config()`
- Toda variable OSIRIS debe tener getter en `app.py` `GET /api/config`
- Toda variable debe tener asignación en `config.py:load_dynamic_config()`

---

## Testing

```bash
# Suite completa
python -m pytest tests/ -v

# Solo imports
python -m pytest tests/test_imports.py -v

# Solo seguridad
python -m pytest tests/test_security.py -v

# Con cobertura
python -m pytest --cov=. --cov-report=term -v
```

### Reglas
- Los tests deben hacer `sys.path.insert(0, ...)` manualmente
- Usar `asyncio_mode = auto` (configurado en pyproject.toml)
- Nombrar tests como `test_*.py` y funciones como `test_*`
- No requieren fixtures complejos — el proyecto no tiene mocking infrastructure

---

## CI Pipeline (GitHub Actions)

4 jobs secuenciales:
1. **lint**: Ruff + mypy (continue-on-error)
2. **test**: pytest con coverage (continue-on-error)
3. **security**: pip-audit (continue-on-error)
4. **deploy-check**: Verifica que todos los módulos importan

Si un job falla, los siguientes continúan igual (continue-on-error: true).

---

## Archivos Críticos — NO MODIFICAR SIN PRECAUCIÓN

| Archivo | Riesgo |
|---|---|
| `app.py` lines 1-50 | Setup de FastAPI, DoH, OpenAI client (NVIDIA API). NO cambiar estructura |
| `app.py` lines 2037-2151 | GET/POST `/api/config` — mantener compatibilidad |
| `config.py` lines 624-855 | `load_dynamic_config()` — cualquier cambio aquí rompe persistencia |
| `config.py` lines 856-900 | `save_dynamic_config()` — escribir archivo + BD |
| `templates/index.html` | Orquestador de partials y scripts — mantener orden |
| `static/js/main.js` | switchTab, CobaltoCore — NO renombrar funciones existentes |
| `static/js/map-unified.js` | Mapa Leaflet unificado — 7 capas OSIRIS + COBALTO con clustering |
| `static/js/osiris-recon.js` | RECON toolkit — 16 herramientas con UI full-page |
| `static/js/osiris-global.js` | CCTV viewer — grid layout, modal expand, metadata panel, SIGINT feed, Aerospace — manejo onerror en JS |
| `osiris_bridge.py` | Router OSIRIS — no cambiar prefijo `/api/osiris` |
