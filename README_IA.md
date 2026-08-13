# COBALTO HUB — Sistema de Inteligencia Artificial

> **Clasificación:** CONFIDENCIAL / USO INTERNO  
> **Versión del sistema:** 9.x  
> **Plataforma:** EL OJO DEL COPORO — C4I

---

## Índice

1. [Visión General](#1-visión-general)
2. [Arquitectura del Motor de IA](#2-arquitectura-del-motor-de-ia)
3. [Proveedores de LLM](#3-proveedores-de-llm)
4. [Motor de Debate Multiagente](#4-motor-de-debate-multiagente)
5. [Pipeline RAG (Retrieval-Augmented Generation)](#5-pipeline-rag)
6. [Módulo de Exportación Word (DOCX)](#6-módulo-de-exportación-word-docx)
7. [Módulo de Exportación PDF](#7-módulo-de-exportación-pdf)
8. [Funciones Analíticas de IA](#8-funciones-analíticas-de-ia)
9. [Resiliencia y Circuit Breaker](#9-resiliencia-y-circuit-breaker)
10. [Configuración](#10-configuración)
11. [API Endpoints](#11-api-endpoints)
12. [Integración en Otros Sistemas](#12-integración-en-otros-sistemas)

---

## 1. Visión General

El sistema de IA de COBALTO HUB es un **motor de análisis de inteligencia multimodal** que combina:

- **Inferencia local** vía Ollama (Llama 3.2 u otros modelos locales)
- **APIs externas** vía NVIDIA NIM (compatible con interfaz OpenAI) usando múltiples claves en pool
- **RAG (Retrieval-Augmented Generation)** sobre la base de datos OSINT local
- **Debate multiagente** con tres perspectivas analíticas independientes *(implementado, actualmente no activo — ver sección 4)*
- **Exportación profesional** a formatos Word (.docx) y PDF

El sistema está diseñado con **fallback automático**: si la IA local falla, pasa a la nube; si la nube falla, retorna al local. Todo con circuit breaker, rate limiting adaptativo y caché en RAM.

---

## 2. Arquitectura del Motor de IA

```
┌─────────────────────────────────────────────────────┐
│                   COBALTO HUB                       │
│                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐  │
│  │ ai_core  │    │ai_local  │    │ollama_provider│  │
│  │  .py     │◄──►│  .py     │◄──►│    .py        │  │
│  └────┬─────┘    └──────────┘    └──────────────┘  │
│       │                                             │
│       ▼                                             │
│  ┌──────────────────────────────────────────────┐   │
│  │           Pool de Clientes LLM               │   │
│  │  [OllamaCompatClient] + [NVIDIA NIM x7 keys] │   │
│  └──────────────────────────────────────────────┘   │
│       │                                             │
│       ▼                                             │
│  ┌────────────────────────────────────────────────┐ │
│  │              rag_retriever.py                  │ │
│  │   FTS5 SQLite + historical_store.py            │ │
│  └────────────────────────────────────────────────┘ │
│       │                                             │
│       ▼                                             │
│  ┌────────────────────────────────────────────────┐ │
│  │             intel_reports.py                   │ │
│  │         Exportador DOCX / PDF                  │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Archivos principales

| Archivo | Rol |
|---|---|
| `ai_core.py` | Motor central: pool de clientes, circuit breaker, debate multiagente, caché |
| `ai_local.py` | Fallback de IA local: Ollama/LM Studio, caché local, extracción de keywords |
| `ollama_provider.py` | Proveedor nativo Ollama: chat, streaming, lista de modelos, `OllamaCompatClient` |
| `rag_retriever.py` | Motor RAG: scoring por relevancia, FTS5, almacenamiento histórico |
| `intel_reports.py` | Centro de informes: investigación IA + exportación DOCX/PDF profesional |

---

## 3. Proveedores de LLM

### 3.1 Ollama (Local — Prioridad 1)

Cuando `OLLAMA_ENABLED=True`, el sistema enruta **primero** a Ollama antes de intentar la nube.

```
Host:    OLLAMA_HOST (default: 192.168.1.213)
Puerto:  OLLAMA_PORT (default: 11434)
Modelo:  OLLAMA_MODEL (default: llama3.2)
Timeout: OLLAMA_TIMEOUT (default: 180s)
```

**Endpoints internos usados:**
- `POST /api/chat` — inferencia conversacional (nativa Ollama)
- `GET /api/tags` — health check y lista de modelos

El `OllamaCompatClient` implementa la misma interfaz que `AsyncOpenAI`, permitiendo su inserción transparente en el pool del `ai_core`.

### 3.2 NVIDIA NIM / Groq (Nube — Prioridad 2)

Pool de hasta **7 claves API** en rotación round-robin:

```
GROQ_API_KEY          → clave genérica principal
GROQ_API_KEY_2        → clave genérica backup
GROQ_API_KEY_3        → clave genérica backup 2
GROQ_API_KEY_COORD    → clave del agente coordinador
GROQ_API_KEY_ARES     → clave dedicada IA-ARES
GROQ_API_KEY_NEXUS    → clave dedicada IA-NEXUS
GROQ_API_KEY_MINERVA  → clave dedicada IA-MINERVA
```

**Base URL:** `https://integrate.api.nvidia.com/v1`  
**Modelo primario:** configurable vía `AI_MODEL` (default: NVIDIA NIM)  
**Modelo fallback:** `meta/llama-3.1-8b-instruct` (activado automáticamente en rate limit 429)

### 3.3 Orden de Fallback

```
1. Ollama Local  →  2. NVIDIA NIM (pool de keys)  →  3. Fallback modelo 8B ligero
```

Si todas las vías fallan, se retorna `"Sin conexión con LLM disponible."`.

---

## 4. Motor de Debate Multiagente

> **⚠️ ESTADO ACTUAL: NO ACTIVO**
> El motor de debate multiagente está **completamente implementado** en `ai_core.py` pero **no se ejecuta en el flujo principal** del sistema en su configuración actual.
>
> **Razón:** El debate requiere ejecutar **3 agentes en secuencia** (ARES → MINERVA → NEXUS), cada uno con su propia llamada de inferencia. Cuando el proveedor es el modelo local (Ollama), esto genera **3 inferencias consecutivas de alto costo** sobre la misma GPU/CPU, saturando el modelo local, aumentando la latencia total del dashboard y pudiendo bloquear otras peticiones concurrentes. Por esta razón se mantiene deshabilitado mientras Ollama sea el proveedor primario.
>
> Puede reactivarse sin cambios de código configurando el trigger correspondiente en `app.py`, preferiblemente cuando se cuente con claves API de nube activas que distribuyan la carga entre los agentes ARES, MINERVA y NEXUS de forma independiente.

### 4.1 Agentes

El sistema implementa **3 agentes analíticos especializados** con perspectivas diferenciadas:

| Agente | Perspectiva | Color UI | Keywords prioritarias |
|---|---|---|---|
| **IA-ARES** | Neutral / Verificación Fáctica (OSINT) | `#00ffaa` | militar, FANB, conflicto, defensa, seguridad |
| **IA-MINERVA** | Oposición / Análisis Crítico | `#44aaee` | gobierno, economía, sanciones, derechos humanos, elecciones |
| **IA-NEXUS** | Oficialismo / Defensa Soberana | `#ff4444` | ciber, desinformación, telecomunicación, satélite, SIGINT |

Cada agente tiene una clave API dedicada para evitar competencia por rate limits.

### 4.2 Pipeline del Debate (Modo `full`)

```
Paso 1: IA-ARES
  └─ Recibe: hasta 15 noticias filtradas por keywords militares/OSINT
  └─ Produce: verificación fáctica objetiva y contextualización

Paso 2: IA-MINERVA
  └─ Recibe: análisis de ARES + hasta 10 noticias de su dominio
  └─ Produce: interpretación crítica desde perspectiva opositora

Paso 3: IA-NEXUS
  └─ Recibe: reporte de ARES + interpretación de MINERVA + contexto propio
  └─ Produce: contraargumentos oficialistas, defensa soberana

Salida: {agents, debate, consensus, mode, timestamp}
```

### 4.3 Modo Express

Alternativa ligera para actualizaciones rápidas del dashboard. Solo usa el agente COORD con 8 noticias y produce un resumen de 3 líneas / 100 palabras máx.

### 4.4 Memoria Táctica

Antes de enviar contexto a los agentes, el sistema inyecta:
- Alertas CRÍTICAS activas del sistema de alertas OSINT
- Títulos de noticias marcadas como Fake News / desinformación probable

### 4.5 Caché de Briefing

Los resultados del debate se cachean por **hash de contexto** (MD5 de los primeros 40 títulos + conteo de alertas/fakenews). El caché tiene un máximo de **10 entradas** en RAM. Si el contexto no cambió, se retorna el debate anterior sin consumir tokens.

---

## 5. Pipeline RAG

### 5.1 Flujo de Recuperación

```
Query del usuario
      │
      ▼
_extraer_palabras_clave()   → elimina stopwords en español
      │
      ▼
_calcular_score_relevancia() por cada entrada:
  • Título:    +4.0 pts por keyword encontrada
  • Entidades: +3.0 pts por keyword en entidad NER
  • Resumen:   +1.5 pts
  • Fuente:    +1.0 pts
      │
      ▼
Ordenar por score desc → Top max_docs (default: 8-10)
      │
      ▼ (Si resultados < max_docs)
historical_store.query_range() → búsqueda FTS5 SQLite
      │
      ▼
Contexto RAG ensamblado → enviado al LLM
```

### 5.2 Estructura del Contexto RAG

Cada documento recuperado se formatea como:

```
[DOC N] Título de la noticia
Fuente: nombre_fuente | URL: https://...
Contenido: resumen/intro (máx 350 chars)
```

### 5.3 Prompt de Investigación Estratégica

El sistema utiliza un **prompt de sistema** estructurado que exige al modelo producir los siguientes apartados:

1. RESUMEN EJECUTIVO
2. HALLAZGOS Y EVIDENCIA FÁCTICA
3. EVALUACIÓN DE AMENAZA Y NIVEL DE ALERTA (`MONITOREO NORMAL` / `ELEVADO` / `CRÍTICO`)
4. IMPACTO OPERATIVO Y VULNERABILIDADES
5. RECOMENDACIONES TÁCTICAS Y PASOS A SEGUIR

---

## 6. Módulo de Exportación Word (DOCX)

### 6.1 Función principal

```python
# intel_reports.py
def generar_docx_informe(datos: InformeIntelData) -> bytes
```

Retorna el documento DOCX serializado en memoria como `bytes` (sin escritura a disco).

### 6.2 Estructura del Documento

```
┌────────────────────────────────────────────────────┐
│  ENCABEZADO                                        │
│  [Logo generado] | EL OJO DEL COPORO              │
│                  | [CONFIDENCIAL - USO INTERNO]   │
│                  | INFORME DE INTELIGENCIA OSINT  │
├────────────────────────────────────────────────────┤
│  METADATA                                          │
│  Código: INT-OSINT-YYYY-NNNN  | Fecha Creación    │
│  Autor: Analista COBALTO IA   | Institución       │
│  Tema: [query] | Fuente Datos: Ollama + RAG        │
├────────────────────────────────────────────────────┤
│  SECCIÓN 1: ANÁLISIS DE INTELIGENCIA IA LOCAL     │
│  NIVEL DE ALERTA: [MONITOREO NORMAL / CRÍTICA]    │
│  [Análisis completo generado por el LLM]          │
├────────────────────────────────────────────────────┤
│  SECCIÓN 2: TARJETAS DE NOTICIAS / EVIDENCIA      │
│  📇 [TARJETA NOTICIOSA #N] Título                 │
│  📡 Fuente | ⚖️ Sentimiento | 🔗 URL              │
│  📝 Resumen noticioso                             │
│  (repetido por cada doc RAG consultado)           │
├────────────────────────────────────────────────────┤
│  SECCIÓN 3: MÉTRICAS BOT SCORE                    │
│  N docs analizados / N con patrones automatizados │
├────────────────────────────────────────────────────┤
│  PIE DE PÁGINA (automático por página)            │
│  EL OJO DEL COPORO - COBALTO HUB | Página N      │
└────────────────────────────────────────────────────┘
```

### 6.3 Estilos y Paleta

| Token | Valor | Uso |
|---|---|---|
| `BG_PAGE` | `#FFFFFF` | Fondo de página (imprimible) |
| `BG_PANEL` | `#F8FAFC` | Fondos de celdas/paneles |
| `ACCENT` | `#0284C7` | Títulos, monospace, links |
| `ROJO` | `#DC2626` | Nivel de alerta crítica, clasificación |
| `TXT` | `#1E293B` | Texto de cuerpo |
| `TXT_DIM` | `#475569` | Labels y metadata |
| `FONT_UI` | `Segoe UI` | Cuerpo del documento |
| `FONT_MONO` | `Courier New` | Código, metadata, encabezados |

### 6.4 Parámetros del Documento

- **Márgenes:** 1.0 pulgada en los 4 lados (estándar legal/profesional)
- **Tablas:** Ancho fijo (`tblLayout=fixed`), sin autofit
- **Fuente base:** Segoe UI 9.5pt, negro oscuro
- **Logo:** Generado en memoria con Pillow (polígono táctico + retícula)
- **Salida:** `io.BytesIO` → `bytes` (sin archivos temporales)

### 6.5 Dependencias requeridas

```
python-docx
Pillow
```

### 6.6 Uso programático

```python
from intel_reports import ejecutar_investigacion_local, generar_docx_informe

# 1. Ejecutar investigación con RAG + Ollama
datos = await ejecutar_investigacion_local(
    query="actividad paramilitar en el Apure",
    preset="general",
    include_rag=True,
    entries_pool=lista_de_noticias  # opcional
)

# 2. Generar bytes DOCX
docx_bytes = generar_docx_informe(datos)

# 3. Enviar como respuesta HTTP
from fastapi.responses import Response
return Response(
    content=docx_bytes,
    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    headers={"Content-Disposition": "attachment; filename=informe.docx"}
)
```

---

## 7. Módulo de Exportación PDF

### 7.1 Función principal

```python
def generar_pdf_informe(datos: InformeIntelData) -> bytes
```

### 7.2 Estructura PDF (A4, portrait)

- **Cabecera:** "EL OJO DEL COPORO - INFORME DE INTELIGENCIA C4I" + `[CONFIDENCIAL]`
- **Bloque metadata:** Código, fecha, autor, nivel de alerta, tema
- **Sección 1:** Análisis completo (markdown limpiado: sin `**`, `###`)
- **Sección 2:** Tarjetas de hasta 6 documentos RAG (con paginación automática)
- **Pie de página:** "COBALTO HUB OSINT | Pagina N"

### 7.3 Dependencias requeridas

```
fpdf2
```

---

## 8. Funciones Analíticas de IA

### 8.1 Geolocalización de texto (`geolocate_text`)

```python
async def geolocate_text(text: str) -> dict  # {"lat": float, "lon": float}
```

**Capa 1 (ultrarrápida):** heurística en RAM vía `dashboard_geocontext.fast_geolocate_venezuela()`  
**Capa 2 (fallback):** LLM con prompt de extracción JSON `{lat, lon}`, temperatura 0.1, 100 tokens  
**Capa 3:** LLM local si Groq falla

### 8.2 Análisis de Sentimiento (`analyze_sentiment`)

```python
async def analyze_sentiment(text: str) -> dict
# {"sentiment": "positivo|negativo|neutral", "score": -1..1, "confidence": 0..100}
```

Temperatura 0.1, 80 tokens, respuesta forzada a JSON object.

### 8.3 Extracción de Entidades NER (`extract_entities`)

```python
async def extract_entities(text: str) -> dict
# {"persons": [], "organizations": [], "locations": [], "events": []}
```

Temperatura 0.1, 150 tokens, respuesta JSON.

### 8.4 Análisis PsyOps (`analyze_psyops_sentiment_async`)

Genera un informe estructurado de Operaciones Psicológicas a partir de los datos de telemetría emocional del corpus:

```json
{
  "operacion_influencia": "Diagnóstico de coordinación / astroturfing",
  "vector_manipulacion": "Táctica cognitiva detectada",
  "contramedida": "Recomendación táctica",
  "nivel_amenaza": "VERDE | AMARILLO | NARANJA | ROJO"
}
```

Usa los datos del módulo `osint_sentiment.py` incluyendo: score global, distribución pos/neg, tasa de bots, clusters CIB, narrativas geopolíticas, palabras negativas top, términos emergentes (Overton).

### 8.5 Análisis en Lote (`analyze_news_batch`)

Procesa hasta **20 noticias en paralelo** con un semáforo de **5 requests concurrentes** para evitar rate limits. Por cada noticia ejecuta sentimiento + NER en paralelo con `asyncio.gather`.

### 8.6 Extracción local de keywords (`extract_keywords_local`)

```python
def extract_keywords_local(text: str, max_keywords: int = 5) -> list
```

Algoritmo basado en frecuencia de términos con lista de stopwords en español. No requiere LLM.

---

## 9. Resiliencia y Circuit Breaker

### 9.1 CircuitBreaker

```python
class CircuitBreaker:
    threshold: int = 5   # fallos consecutivos para abrir
    recovery: float = 60.0  # segundos hasta intentar reabrir
```

**Estados:**
- `CLOSED` — operación normal
- `OPEN` — bloqueado tras N fallos, rechaza solicitudes
- `HALF_OPEN` — prueba tras el timeout, si tiene éxito vuelve a CLOSED

### 9.2 Rate Limiting Adaptativo (`ai_adaptive_call`)

Decorador que aplica backoff exponencial con jitter aleatorio:

```
Retry 1: espera 2^1 + random(0,1) segundos
Retry 2: espera 2^2 + random(0,1) segundos
Retry 3: espera 2^3 + random(0,1) segundos
→ máximo 3 reintentos, luego retorna None
```

Integrado con `RATE_LIMITERS["ai_groq"]` del módulo `humanization.py`.

### 9.3 Pool de Keys con Penalización

Cada clave API tiene un contador de fallos consecutivos. Si una clave supera **3 fallos**, se salta en la rotación. Cuando todas las claves están penalizadas, se resetean los contadores y se reintenta desde la primera.

### 9.4 Caché en RAM

| Caché | Capacidad | Evicción |
|---|---|---|
| `_ai_cache` (resultados generales) | 5000 entradas | FIFO: elimina 20% al llegar al límite |
| `_briefing_cache` (debates) | 10 entradas | Clear total al llegar al límite |
| `_local_cache` en `ai_local.py` | 200 entradas | Elimina primeras 50 al llegar al límite |

La clave de caché es un MD5 del texto de entrada con prefijo por tipo (`geo:`, `sent:`, `ner:`, `psyops:`, `local:`).

### 9.5 Sesión aiohttp compartida

Una sola `aiohttp.ClientSession` reutilizable por toda la vida del proceso, con `timeout=30s` y `User-Agent: CobaltoHub-AI/9.0`. Cerrada de forma segura en el shutdown del servidor.

---

## 10. Configuración

### Variables en `config.py` (prefijo `AI_` y `OLLAMA_`)

| Variable | Descripción | Default |
|---|---|---|
| `AI_MODEL` | Modelo primario NVIDIA/Groq | (ver config.py) |
| `AI_TEMPERATURE` | Temperatura de generación | 0.3 |
| `AI_MAX_TOKENS` | Tokens máx para debate | 1000+ |
| `AI_SYSTEM_PROMPT_ARES` | Instrucción de lineamiento ARES | (definida en config) |
| `AI_SYSTEM_PROMPT_MINERVA` | Instrucción de lineamiento MINERVA | (definida en config) |
| `AI_SYSTEM_PROMPT_NEXUS` | Instrucción de lineamiento NEXUS | (definida en config) |
| `OLLAMA_ENABLED` | Activar inferencia local | `True` |
| `OLLAMA_HOST` | IP del servidor Ollama | `192.168.1.213` |
| `OLLAMA_PORT` | Puerto del servidor Ollama | `11434` |
| `OLLAMA_MODEL` | Nombre del modelo local | `llama3.2` |
| `OLLAMA_TIMEOUT` | Timeout de inferencia local (s) | `180` |
| `PREFER_LOCAL_AI` | Priorizar local sobre nube | `True` |

Todas las variables son configurables dinámicamente desde el **Panel de Configuración** del dashboard (subtab OSIRIS Engine) via `POST /api/config`, sin necesidad de reiniciar el servidor.

---

## 11. API Endpoints

### Endpoints de IA / Informes

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/briefing` | Genera/retorna el debate multiagente actual |
| `GET` | `/api/briefing/step` | Estado de progreso del debate en curso |
| `POST` | `/api/intel/investigate` | Ejecuta investigación RAG + Ollama |
| `GET` | `/api/intel/export/docx` | Descarga el último informe en formato Word |
| `GET` | `/api/intel/export/pdf` | Descarga el último informe en formato PDF |
| `GET` | `/api/ollama/status` | Health check de Ollama + lista de modelos |
| `POST` | `/api/rag/query` | Consulta directa al motor RAG |

### Parámetros de investigación (`POST /api/intel/investigate`)

```json
{
  "query": "tema de investigación",
  "preset": "general | militar | economico | ciber",
  "include_rag": true,
  "export_format": "docx | pdf | json"
}
```

---

## 12. Integración en Otros Sistemas

### 12.1 Importar el motor RAG

```python
import sys
sys.path.insert(0, "/ruta/a/cobalto")

from rag_retriever import retrieve_relevant_entries, build_rag_prompt

# Recuperar documentos relevantes
docs = retrieve_relevant_entries(
    query="actividad irregular en la frontera",
    entries=mi_lista_de_noticias,
    max_docs=8
)

# Construir prompt listo para enviar a cualquier LLM
prompt = build_rag_prompt(query="...", docs=docs)
```

### 12.2 Importar el generador de informes

```python
import asyncio
from intel_reports import ejecutar_investigacion_local, generar_docx_informe, generar_pdf_informe

async def generar_informe(tema: str) -> bytes:
    datos = await ejecutar_investigacion_local(query=tema)
    return generar_docx_informe(datos)  # o generar_pdf_informe(datos)

docx_bytes = asyncio.run(generar_informe("acciones militares en el Arco Minero"))
with open("informe.docx", "wb") as f:
    f.write(docx_bytes)
```

### 12.3 Importar solo la capa de LLM

```python
from ollama_provider import ollama_chat, ollama_settings

# Configurar (o usar los valores de config.py)
cfg = ollama_settings()
print(f"Conectando a Ollama en {cfg['base_url']} — modelo: {cfg['model']}")

# Llamar al modelo
import asyncio
respuesta = asyncio.run(ollama_chat(
    messages=[{"role": "user", "content": "Analiza la situación en Venezuela"}],
    model=cfg["model"],
    temperature=0.3,
    max_tokens=500
))
print(respuesta)
```

### 12.4 Requisitos mínimos para integración

```
python >= 3.11
aiohttp
openai           # para interfaz AsyncOpenAI compatible
python-docx      # para exportación Word
fpdf2            # para exportación PDF
Pillow           # para logo en DOCX
python-dotenv
```

### 12.5 Variables de entorno mínimas

```env
# Para IA local (Ollama)
OLLAMA_ENABLED=true
OLLAMA_HOST=192.168.1.213
OLLAMA_PORT=11434
OLLAMA_MODEL=llama3.2

# Para IA en nube (al menos una clave)
GROQ_API_KEY=nvapi-xxxxxxxxxxxxxxxx
```

### 12.6 Estructura de datos: `InformeIntelData`

```python
@dataclass
class InformeIntelData:
    codigo: str                  # "INT-OSINT-2026-0042"
    fecha_creacion: str          # "12/08/2026 15:30"
    autor: str                   # "Analista COBALTO IA (Local)"
    institucion: str             # "EL OJO DEL COPORO / C4I"
    fuente_datos: str            # "Ollama (llama3.2) + RAG Local (8 docs)"
    fecha_analisis: str
    tema_investigacion: str      # query original del usuario
    resumen_ejecutivo: str       # primeros 350 chars del análisis
    analisis_completo: str       # análisis full del LLM
    nivel_alerta: str            # "MONITOREO NORMAL" | "ALERTA ELEVADA" | "ALERTA CRÍTICA"
    documentos: List[DocumentoIntel]
    total_analizados: int
    doc_con_bot: int
    niveles_bot: list
    fuentes_bot: list
```

---

## Notas de Seguridad

- El análisis IA opera sobre datos **ya sanitizados** por `security_utils.sanitize_html()` antes de retornarse al frontend.
- Las claves API se almacenan exclusivamente en variables de entorno (`.env`), nunca en el código fuente.
- El contenido del análisis IA se trunca a 40,000 chars máx antes de enviar al LLM para prevenir errores HTTP 413.
- El modo de debate multiagente incluye un hash de contexto para evitar re-debates idénticos (ahorro de tokens y latencia).

---

*Documento generado automáticamente a partir del análisis del repositorio COBALTO HUB v9.x.*  
*Para uso exclusivo en integración con sistemas C4I compatibles.*
