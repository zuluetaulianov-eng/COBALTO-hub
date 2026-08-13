# COBALTO — Generador de Reportes OSINT Enterprise

Sistema full-stack para la generación automatizada de reportes de patrullaje digital con análisis de inteligencia artificial (Groq Llama 3.3) estructurado y base de datos OSINT asíncrona integrada.

---

## Estructura del proyecto

```
BOTDOCUMENTO/
├── .env.example              # Variables de entorno (template)
├── requirements.txt          # Dependencias Python (FastAPI, aiosqlite, docxtpl...)
├── pyproject.toml            # Configuración del paquete Python
│
├── backend/
│   ├── main.py               # Punto de entrada FastAPI + lifespan
│   ├── config.py             # Settings desde variables de entorno
│   ├── db/
│   │   └── osint.db          # Base de datos SQLite (aiosqlite + FTS5)
│   ├── templates/
│   │   └── template_reporte.docx # Plantilla base de Microsoft Word (Jinja2)
│   ├── models/
│   │   ├── reporte.py        # ReporteRequest, GenerarWordRequest, AnalisisIA (estricto)
│   │   └── osint.py          # OsintEntry, OsintSearchParams
│   ├── routers/
│   │   ├── reportes.py       # POST /analizar-ia y POST /generar-word
│   │   └── osint.py          # GET /api/osint/entries, /api/osint/tags
│   ├── services/
│   │   ├── groq_service.py   # Groq AI JSON Mode (semáforo 3 hilos + fallback)
│   │   ├── docx_service.py   # Renderizado docxtpl con imágenes dinámicas
│   │   └── osint_service.py  # Consultas asíncronas FTS5 aiosqlite
│   └── middleware/
│       └── auth.py           # Bearer token opcional
│
├── frontend/src/app/
│   ├── components/
│   │   └── cobalto-report/
│   │       ├── cobalto-report.component.ts    # Lógica (Input -> Preview -> Document)
│   │       ├── cobalto-report.component.html  # Interfaz Glassmorphism
│   │       ├── cobalto-report.i18n.ts         # Español / Inglés
│   │       ├── cobalto-report.model.ts        # Interfaces TypeScript
│   │       └── index.ts                       # Barrel export
│   └── services/
│       └── reporte.service.ts  # Cliente HTTP RxJS
│
└── tests/
    ├── test_auth.py
    ├── test_docx_service.py
    ├── test_groq_service.py
    ├── test_osint.py
    └── test_reportes.py
```

---

## Funcionamiento

### Flujo Principal (Generación en 2 Pasos)

El sistema ahora soporta un flujo de revisión humana "Human-in-the-Loop" antes de ensamblar el documento oficial.

```
Paso 1: Previsualización de Inteligencia Artificial
Usuario completa formulario
       │
       ▼
   Backend recibe POST /api/reportes/analizar-ia
       │
       ├─ Valida payload estrictamente (Pydantic)
       │
       ├─ Por cada novedad:
       │    └─ Groq AI evalúa y devuelve JSON (Actores, Amenaza, Análisis)
       │
       └─ Devuelve `list[AnalisisIA]` al Frontend
       
Paso 2: Revisión y Generación Documental
Frontend permite al usuario editar/corregir el JSON propuesto por la IA
       │
       ▼
   Backend recibe POST /api/reportes/generar-word
       │
       ├─ docxtpl abre `backend/templates/template_reporte.docx`
       ├─ httpx descarga imágenes y crea InlineImages
       ├─ Jinja2 renderiza las variables `{{ analisis.actores }}`, etc.
       │
       └─ Responde .docx binario → el frontend lo descarga
```

### Flujo OSINT (Base de conocimiento FTS5)

El motor OSINT utiliza **aiosqlite** para no bloquear el Event Loop y una tabla virtual **FTS5** sincronizada mediante _triggers_ para realizar búsquedas textuales de máximo rendimiento usando la directiva `MATCH "palabra*"`.

```
Frontend   ←→   GET /api/osint/entries?tag=&q=&limit=&offset=
                 GET /api/osint/tags
                     │
                     ▼
                 SQLite asíncrono (backend/db/osint.db)
                 - Auto-semilla inicial si está vacía
                 - Tabla virtual `osint_fts` para búsquedas en sub-cadenas rápidas
```

### Arquitectura backend

| Capa | Tecnología | Rol |
|------|-----------|-----|
| Servidor | FastAPI + Uvicorn | Rutas REST, validación estricta (HttpUrl, min_length) |
| Base de datos | SQLite asíncrono (`aiosqlite`) | OSINT entries, tabla FTS5, triggers |
| IA | Groq SDK | Análisis estructurado en JSON (Fallback + Semáforo) |
| Documentos | `docxtpl` (Jinja2) | Generación dinámica sobre plantilla Word física |
| HTTP | `httpx.AsyncClient` | Descarga de imágenes asíncronas |
| Logging | `logging` | Auditoría de IPs, errores IA y peticiones |

### Arquitectura frontend

| Capa | Tecnología | Rol |
|------|-----------|-----|
| Framework | Angular 17+ standalone | Componente autónomo, OnPush |
| Estado | Signals (`signal()`) | Fases (`input` -> `preview`), progreso visual |
| Formulario | `ngModel` + `<form>` | Two-way binding, Enter/Ctrl+Enter submit |
| Resiliencia | RxJS | Manejo avanzado de `Blob` vs `JSON` en `catchError` |

---

## Implementación en otros proyectos

### Como componente Angular

El frontend es un **componente standalone** publicable como librería.

```bash
npm install cobalto-reportes-frontend
```

```typescript
// app.module.ts o standalone component
import { CobaltoReportComponent } from 'cobalto-reportes-frontend';

// Template
<lib-cobalto-report
  [maxNovedades]="3"
  lang="es"
  mode="full"
  apiBaseUrl="http://localhost:8000"
  [authToken]="'mi-token-seguro'"
/>
```

### Como API REST independiente

```bash
# Previsualizar análisis de IA
curl -X POST "http://localhost:8000/api/reportes/analizar-ia" \
  -H "Content-Type: application/json" \
  -d '{
    "novedades": [{
      "fecha_situacion": "17JUN2026",
      "portal_web_url": "https://ejemplo.com",
      "texto_situacion": "...",
      "imagenes": []
    }]
  }'

# Generar reporte final (Word)
curl -X POST "http://localhost:8000/api/reportes/generar-word" \
  -H "Content-Type: application/json" \
  -d '{
    "novedades": [{ ... }],
    "analisis_por_novedad": [{
       "actores": ["Hacker"], 
       "amenaza": "Alta", 
       "analisis": "Análisis modificado por analista"
    }]
  }' \
  --output Reporte_Cobalto.docx
```

### Despliegue Backend

```bash
pip install -r requirements.txt
cp .env.example .env   # Editar GROQ_API_KEY
python -m backend.main
```

Variables de entorno clave:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | **Requerida.** API key de Groq |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Modelo de IA configurado para `json_object` |
| `AUTH_ENABLED` | `false` | Activar autenticación Bearer |
| `AUTH_TOKEN` | — | Token compartido estático |
| `CORS_ORIGINS` | `*` | Orígenes permitidos |

#### Pruebas Unitarias

```bash
pytest tests/ -v
# 29 tests — cobertura integral con mocks (auth, docxtpl, groq, aiosqlite, routers)
```

### Notas técnicas y resiliencia

- **Resiliencia Pydantic:** Se exige `min_length` y validación URL en origen para evitar que la IA o el docxtpl fallen internamente.
- **Resiliencia IA:** Si Groq ignora el JSON Mode, un _fallback_ intercepta la cadena cruda empaquetándola en un objeto válido transparente para el docxtpl.
- **Resiliencia Docx:** Las imágenes inaccesibles (errores HTTP, Timeouts) se descartan asíncronamente en lugar de romper el ciclo de compilación de la plantilla.
