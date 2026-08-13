# 🦅 EL OJO DEL COPORO — Chat IA Local + Informe OSINT

> Interfaz gráfica para Windows que combina dos módulos:
> 1. **Chat con modelos de IA local** vía Ollama (streaming en tiempo real).
> 2. **Generador de informes de inteligencia OSINT** en formato Word (`.docx`)
>    con diseño cyber/dark-mode y origen de datos multifuente resiliente.
>
> Proyecto del pipeline de análisis documental **CobaltoIA**.

---

## 📋 Índice

- [Descripción](#-descripción)
- [Características clave](#-características-clave)
- [Estructura de funcionamiento](#-estructura-de-funcionamiento)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Requisitos del sistema](#-requisitos-del-sistema)
- [Instalación y uso](#-instalación-y-uso)
- [Origen de datos del informe](#-origen-de-datos-del-informe)
- [Detalles técnicos del DOCX](#-detalles-técnicos-del-docx)
- [API utilizada](#-api-utilizada)
- [Guía de temperatura](#-guía-de-temperatura)
- [Modelos probados](#-modelos-probados-y-compatibles)
- [Solución de problemas](#-solución-de-problemas)
- [Hoja de ruta — App Android](#-hoja-de-ruta--próxima-versión-app-android)
- [Autor](#-autor)

---

## 📌 Descripción

**El Ojo del Coporo** es una aplicación de escritorio para Windows construida en
Python que sirve como herramienta de evaluación del proyecto **CobaltoIA**:

- Evalúa modelos de lenguaje locales (Ollama) antes de integrarlos al pipeline.
- Genera informes de inteligencia OSINT en Word con estética cibernética/dark-mode,
  exportables con un solo botón y alimentados por múltiples fuentes de datos
  (JSON, SQLite, MongoDB, PostgreSQL) con conmutación automática ante fallos.

---

## ✨ Características clave

### 💬 Módulo de chat (Tkinter)

| Función | Detalle |
|---|---|
| 🌐 **Conexión en red local** | Se conecta a cualquier servidor Ollama por IP y puerto |
| 📡 **Streaming en tiempo real** | Los tokens aparecen letra a letra mientras el modelo genera |
| 🔌 **Modo síncrono** | Alternativa sin streaming con el mismo resultado |
| 🔍 **Auto-detección de modelos** | Consulta `GET /api/tags` y lista los modelos disponibles |
| 🌡️ **Control de temperatura** | Slider de 0.0 a 2.0 para ajustar creatividad del modelo |
| 💬 **System prompt configurable** | Define el comportamiento base del asistente |
| 👤 **Nombre de usuario editable** | Tu nombre aparece como prefijo en el chat |
| 🗑️ **Limpiar historial** | Resetea el contexto para una nueva sesión |
| ⏱️ **Métricas de respuesta** | Muestra tokens acumulados y tiempo de generación |
| ⌨️ **Atajos de teclado** | `Enter` = Enviar, `Shift+Enter` = Salto de línea |
| 🎨 **Color por roles** | Usuario (azul), Ollama (verde), sistema (gris), errores (rojo) |
| ⚡ **UI no bloqueante** | Toda la red corre en `threading.Thread` daemon |

### 📄 Módulo de informe OSINT

| Función | Detalle |
|---|---|
| ⬇️ **Exportar informe** | Genera `informe_inteligencia_coporo.docx` con diseño OSINT |
| 💬 **Exportar IA** | Genera `transcripcion_ia.docx` con la conversación sostenida con el modelo |
| 🌗 **Dark-mode nativo** | Fondo `#0D1117`, tarjetas `#161B22`, acentos neón |
| 🗂️ **Tarjetas de documentos** | Cada noticia en módulos independientes con análisis de inteligencia |
| 📊 **Tablas estadísticas** | Distribución por bot score y fuentes con mayor actividad de bot |
| 🏷️ **Logo vectorial generado** | Emblema dibujado en memoria con Pillow (sin archivos externos) |
| 🔢 **Numeración de páginas** | Pie de página con campo `PAGE` de Word |
| 🔀 **Multifuente resiliente** | JSON, SQLite, MongoDB, PostgreSQL o ejemplo, con **failover** |
| 🔒 **Sin dejar residuos** | El logo temporal se limpia con `finally` |

---

## 🏗️ Estructura de funcionamiento

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CAPA DE PRESENTACIÓN (UI)                        │
│                          chat_ollama.py (Tkinter)                       │
│  ┌───────────┐   ┌──────────────┐   ┌───────────────┐   ┌────────────┐  │
│  │  Detectar │   │   Chat (API  │   │   Limpiar     │   │  Exportar  │  │
│  │  modelos  │   │   Ollama)    │   │   historial   │   │  informe   │  │
│  └───────────┘   └──────────────┘   └───────────────┘   └────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ threading (no bloquea la UI)
┌──────────────────────────────▼──────────────────────────────────────────┐
│                CAPA DE ORIGEN DE DATOS  (fuente_datos.py)               │
│                                                                         │
│     cargar_informe() → OrigenCompuesto → construye adaptadores          │
│          en el orden definido por config_fuente.json                    │
│                                                                         │
│   [json] [sqlite] [mongo] [postgres] [ejemplo]   ← reordena aquí        │
│       └── usa el PRIMERO que responda ──┐                               │
│                                          ▼                              │
│                                 ResultadoCarga                          │
│                          (datos + origen + resumen + errores)           │
└──────────────────────────────┬──────────────────────────────────────────┘
                               ▼
┌──────────────────────────────▼──────────────────────────────────────────┐
│                  CAPA DE MODELO DE DATOS (informe_osint.py)             │
│                                                                         │
│   InformeData ──to_dict()/from_dict()──► JSON intermedio                │
│   Documento   (doc_num, titulo, fuente, score, url, analisis, ...)      │
└──────────────────────────────┬──────────────────────────────────────────┘
                               ▼
┌──────────────────────────────▼──────────────────────────────────────────┐
│                CAPA DE RENDERIZADO DOCX (python-docx)                   │
│                                                                         │
│   generar_informe_osint(datos, output)                                  │
│     ├─ w:background + w:displayBackgroundShape  → fondo oscuro visible  │
│     ├─ Tabla 1×2 encabezado  (logo + título)                            │
│     ├─ Tabla 3×2 metadatos    (código, autor, fuente, ...)              │
│     ├─ Tarjetas por documento (tabla 1×1 + w:cantSplit)                 │
│     │    └─ Caja verde de análisis de inteligencia (tabla anidada)      │
│     ├─ Tablas de bots          (niveles + fuentes con encabezado)       │
│     └─ Pie de página con campo PAGE                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Flujo de datos end-to-end

```
Botón "⬇ Exportar informe"
        │
        ▼
cargar_informe(config_fuente.json)      ← capa origen (failover)
        │  ResultadoCarga { datos, origen, resumen, errores }
        ▼
generar_informe_osint(resultado.datos)  ← capa render
        │
        ▼
informe_inteligencia_coporo.docx
        │
        ▼
ecos en el chat:  origen usado + advertencias de failover
```

### ¿Por qué esta arquitectura?

- **Desacoplamiento por capas:** la UI no sabe de dónde vienen los datos; el
  generador no sabe cómo se conectan; el origen no sabe cómo se renderizan.
- **Resiliencia:** si MongoDB cae y no hay JSON, el informe se genera igual con
  los datos que estén disponibles (o con ejemplo), avisando siempre al usuario.
- **Serialización libre:** `InformeData`/`Documento` se convierten a JSON con
  `to_dict()`/`from_dict()`, lo que permite persistir, transportar o exponer
  los datos por API sin tocar la lógica de render.
- **Extensible:** agregar un nuevo origen (ej: API REST) solo requiere una nueva
  clase `BaseOrigen` y una línea en la fábrica `construir_origenes()`.

---

## 📁 Estructura del proyecto

```
Ollama_Interfaz_Windows/
│
├── chat_ollama.py        ← Aplicación principal (Python + Tkinter)
├── informe_osint.py      ← Generador del informe DOCX (modelo + render)
├── fuente_datos.py       ← Capa de orígenes de datos con failover
├── chat_docx.py          ← Generador de transcripción de conversación IA (.docx)
│
├── config_fuente.json    ← Configuración de prioridad de orígenes
├── datos_informe.json    ← Datos de ejemplo (fuente JSON por defecto)
├── schema_documentos.sql ← Esquema de referencia para SQLite/PostgreSQL
│
├── Iniciar_Chat.bat      ← Lanzador para Windows (doble clic)
├── Instrucciones.txt     ← Guía rápida de uso
└── README.md             ← Este archivo
```

---

## 🖥️ Requisitos del sistema

### En Windows (cliente)

| Componente | Requerimiento |
|---|---|
| **Python** | 3.8 o superior ([python.org](https://www.python.org/downloads/)) |
| **Tkinter** | Incluido por defecto en Python para Windows |
| **Chat** | Sin librerías externas (`urllib`, `json`, `threading`) |
| **Exportar informe** | `python-docx` + `Pillow` (instalados automáticamente por el `.bat`) |
| **MongoDB** *(opcional)* | `pip install pymongo` |
| **PostgreSQL** *(opcional)* | `pip install psycopg2-binary` |

### En el servidor (Xubuntu u otro equipo)

- **Ollama instalado y corriendo** — [ollama.com](https://ollama.com/)
- Al menos un modelo descargado (ej: `ollama pull llama3.2`)
- Puerto `11434` accesible en la red local
- IP conocida (por defecto configurada: `192.168.1.213`)

---

## 🚀 Instalación y uso

### 1. Iniciar el servidor Ollama (en Xubuntu)

```bash
ollama serve            # Verificar que esté corriendo
ollama list             # Listar modelos disponibles
ollama pull llama3.2    # Descargar un modelo si no tienes ninguno
```

### 2. Iniciar la interfaz (en Windows)

```
Doble clic en:  Iniciar_Chat.bat
```

El lanzador verifica Python, instala `python-docx` y `Pillow` la primera vez e
inicia la interfaz. Alternativa manual:

```powershell
pip install python-docx pillow     # solo la primera vez, opcional
python chat_ollama.py
```

### 3. Configurar la interfaz

1. Ingresa tu **nombre** en el campo "Tu nombre"
2. Verifica la **IP** del servidor Ollama
3. Confirma el **puerto** (por defecto: `11434`)
4. Pulsa **⟳ Detectar** para cargar los modelos disponibles
5. Ajusta la **temperatura** según el tipo de respuesta que necesitas
6. Opcionalmente edita el **System Prompt**
7. ¡Escribe tu mensaje y pulsa **Enviar**!

### 4. Exportar el informe

1. Pulsa **⬇ Exportar informe**
2. Observa el estado: "Generando informe…"
3. Al terminar verás la ruta del `.docx` y el **origen de datos** que se usó
4. Versión documental: la exportación respeta el **mismo orden** a través de la
   capa de datos — puedes exportar tantas veces como necesites sin abrir Word.

---

## 📚 Origen de datos del informe

El informe es **multifuente con conmutación automática (failover)**. El sistema
intenta los orígenes **en el orden** definido en `config_fuente.json` (campo
`"orden"`) y usa el primero que responda. Si todos fallan, regresa al modo de
ejemplo para nunca dejar sin informe al usuario.

### Orígenes soportados

| Origen | Backend | Requiere instalar |
|---|---|---|
| `json` | Archivo JSON (por defecto: `datos_informe.json`) | nada |
| `sqlite` | Base SQLite local (`datos_informe.db`) | nada (stdlib) |
| `mongo` | MongoDB (colección `documentos`) | `pip install pymongo` |
| `postgres` | PostgreSQL (tabla `documentos`) | `pip install psycopg2-binary` |
| `ejemplo` | Datos incrustados (último recurso) | nada |

### Cambiar el origen

Edita `config_fuente.json`. Ejemplo para priorizar la base local:

```json
{
  "orden": ["sqlite", "json", "ejemplo"]
}
```

Cada origen mapea sus columnas/campos a los mismos nombres que en
`datos_informe.json` (`doc_num`, `titulo`, `fuente`, `analisis`, `contenido`, ...).
El esquema de referencia para SQL está en `schema_documentos.sql`.

### Configuración de cada origen

```jsonc
{
  "orden": ["json", "sqlite", "mongo", "postgres", "ejemplo"],
  "fallback": true,                          // true = nunca fallar en seco
  "json":     { "ruta": "datos_informe.json" },
  "sqlite":   { "ruta": "datos_informe.db", "tabla_docs": "documentos", "tabla_meta": "informe_meta" },
  "mongo":    { "uri": "mongodb://localhost:27017", "base": "el_ojo_coporo", "coleccion": "documentos" },
  "postgres": { "conn_info": "postgresql://postgres:postgres@localhost:5432/el_ojo_coporo", "tabla": "documentos" }
}
```

### Validación y advertencias en el chat

- Cada origen se instancia de forma **aislada**: si uno lanza error, se registra
  en `ResultadoCarga.errores` y se pasa al siguiente.
- Al exportar, la UI muestra: `Origen de datos: <resumen>` y una línea
  `Advertencia:` por cada origen que falló — transparente para el usuario final.

---

## 🔬 Detalles técnicos del DOCX

### Informe OSINT (`informe_osint.py`)

La generación usa **python-docx** con manipulación de OXML para lograr un diseño
que Word no ofrece de forma nativa:

| Técnica | Cómo se implementa |
|---|---|
| **Fondo de página oscuro** | `<w:background w:color="0D1117">` + `<w:displayBackgroundShape>` en settings (para que sea visible en pantalla) |
| **Tarjetas (cards)** | Tablas de 1 fila × 1 columna con `w:shd` (sombreado `#161B22`) y `w:tcBorders` (`#30363D`) |
| **No cortar cards entre páginas** | `w:cantSplit` aplicado a cada fila de tarjeta |
| **Caja verde de análisis** | Tabla anidada dentro de la tarjeta, borde `#238636` y fondo `#0D1117` |
| **Colspan real** | `cell.merge()` para la fila "Fuente de Datos" |
| **Logo sin archivos fijos** | Dibujado en memoria con Pillow → PNG temporal → se borra en `finally` |
| **Numeración de páginas** | Campo de Word `PAGE` en el pie de página |
| **Saltos de línea** | `run.add_break()` (evita el bug de `\n` dentro de `w:t`) |
| **Orden OXML válido** | `tcBorders` se inserta antes de `shd` para no corromper el esquema |

### Transcripción de IA (`chat_docx.py`)

Exporta la conversación sostenida con el modelo como documento estilizado:

| Elemento | Detalle |
|---|---|
| **Cabecera** | Mismo emblema "EL OJO DEL COPORO" + etiqueta CONFIDENCIAL |
| **Tabla de metadatos** | Usuario, modelo, temperatura, fecha y nº de mensajes |
| **Tarjetas por mensaje** | Consulta del usuario (borde azul `#58A6FF`) y respuesta del modelo (borde verde `#238636` + título "OLLAMA ▸ ANÁLISIS DE IA") |
| **Resumen de sesión** | Tabla estadística con consultas, respuestas y palabras totales |
| **Reutilización de OXML** | Importa los helpers de `informe_osint.py` (fondo, paginación, `cantSplit`, estilos) |

El modelo de datos (`ChatData` + `MensajeChat`) también es serializable a JSON con
`to_dict()`/`from_dict()`, y `chat_desde_historial()` convierte el historial de la
app directamente en el documento.

### Paleta visual

| Rol | Color |
|---|---|
| Fondo de página | `#0D1117` |
| Tarjetas / paneles | `#161B22` |
| Acentos principales | `#58A6FF` / `#1F6FEB` |
| Análisis de inteligencia | `#3FB950` / `#238636` |
| Etiqueta CONFIDENCIAL | `#DA3633` |
| Texto base | `#C9D1D9` |
| Bordes | `#30363D` |

---

## 🔌 API utilizada

La interfaz se comunica con la API REST de Ollama:

| Endpoint | Método | Uso |
|---|---|---|
| `/api/tags` | `GET` | Listar modelos disponibles |
| `/api/chat` | `POST` | Enviar mensajes y recibir respuestas |

Ejemplo de payload enviado:

```json
{
  "model": "llama3.2",
  "messages": [
    {"role": "system", "content": "Eres un asistente útil."},
    {"role": "user",   "content": "¿Qué es la entropía?"}
  ],
  "stream": true,
  "options": { "temperature": 0.7 }
}
```

---

## 🌡️ Guía de temperatura

| Valor | Comportamiento | Ideal para |
|---|---|---|
| `0.0 – 0.3` | Muy determinista, respuestas exactas | Análisis de datos, código, hechos |
| `0.4 – 0.7` | Equilibrado | Conversación general |
| `0.8 – 1.2` | Creativo, variado | Redacción, brainstorming |
| `1.3 – 2.0` | Muy aleatorio, experimental | Pruebas de límites del modelo |

---

## 🛠️ Modelos probados y compatibles

| Modelo | Tamaño aprox. | Notas |
|---|---|---|
| `llama3.2` | 2 GB | ✅ Rápido, buena calidad general |
| `llama3` | 4.7 GB | ✅ Mayor capacidad de razonamiento |
| `mistral` | 4.1 GB | ✅ Excelente para texto en español |
| `gemma2` | 5 GB | ✅ Bueno para análisis estructurado |
| `phi3` | 2.3 GB | ✅ Muy eficiente en recursos |
| `qwen2` | 4.4 GB | ✅ Multilingüe, buen soporte en español |

---

## ⚠️ Solución de problemas

**Error: "Error de conexión"**
- Verifica que Ollama esté corriendo en el servidor: `ollama serve`
- Confirma que la IP y el puerto sean correctos
- Asegúrate de que el firewall no bloquee el puerto `11434`

**No aparecen modelos al detectar**
- El servidor está en línea pero no tiene modelos descargados
- Ejecuta en el servidor: `ollama pull llama3.2`

**El informe exporta con datos de ejemplo**
- El origen configurado primero no estaba disponible (revisa `config_fuente.json`)
- El chat te dirá exactamente qué orígenes fallaron en las líneas `Advertencia:`

**Error "pymongo no instalado" / "psycopg2 no instalado"**
- Instala el driver del origen que configuraste: `pip install pymongo` o `pip install psycopg2-binary`
- O quita ese origen del campo `"orden"` en `config_fuente.json`

**El fondo oscuro no se ve al imprimir desde Word**
- Es normal: Word requiere activar "Imprimir colores de fondo e imágenes"
  (Archivo → Opciones → Mostrar) para incluir el fondo al imprimir/exportar PDF.

**La respuesta tarda mucho**
- Normal para modelos grandes en hardware limitado
- Prueba con `phi3` o `llama3.2` (modelos más livianos)
- Reduce el system prompt para menor contexto inicial

---

## 📱 Hoja de Ruta — Próxima Versión: App Android

> **Estado:** En planificación. Se tomará la **Opción A (Flutter)**.

### Opciones evaluadas

| # | Tecnología | Descripción | Estado |
|---|---|---|---|
| **A ⭐** | **Flutter** | App nativa Android/iOS con Material Design 3. Streaming real, UI premium. | ✅ **SELECCIONADA** |
| B | Kotlin Nativo | App 100% nativa Android. Máximo rendimiento. Requiere Android Studio. | 🔄 Descartada por ahora |
| C | PWA (Web App) | Web app instalable desde el navegador. Sin compilar. Más limitada. | 🔄 Descartada por ahora |

### ¿Por qué Flutter?

- ✅ UI nativa de calidad profesional (Material Design 3)
- ✅ Streaming HTTP integrado (`http` package con `StreamedResponse`)
- ✅ Un solo código para Android, iOS y Windows
- ✅ Hot reload para desarrollo rápido
- ✅ Gran ecosistema de paquetes

### Plan de desarrollo de la App Android

#### Fase 1 — Setup del entorno
- [ ] Instalar **Android Studio** → [developer.android.com/studio](https://developer.android.com/studio)
- [ ] Instalar **Flutter SDK** → [flutter.dev/docs/get-started/install/windows](https://flutter.dev/docs/get-started/install/windows)
- [ ] Configurar emulador Android o conectar dispositivo físico
- [ ] Verificar con `flutter doctor` que todo está correcto

#### Fase 2 — Funcionalidades de la App
- [ ] Pantalla de configuración (IP, puerto, modelo)
- [ ] Chat con streaming en tiempo real
- [ ] Historial de conversaciones guardado localmente (SQLite)
- [ ] Selector de modelos con auto-detección
- [ ] Control deslizante de temperatura
- [ ] Modo claro / modo oscuro
- [ ] Soporte para múltiples conversaciones (pestañas o cajón)
- [ ] Exportar conversación como `.txt` o `.md`

#### Fase 3 — Pulido y distribución
- [ ] Icono de app personalizado
- [ ] Pantalla de splash
- [ ] Generar APK firmado para instalación directa
- [ ] (Opcional) Publicar en Google Play

### Instalación previa requerida

```powershell
# 1. Instalar Flutter (tras descargar el SDK)
# Agregar C:\flutter\bin al PATH del sistema

# 2. Verificar instalación
flutter doctor

# 3. Crear proyecto
flutter create ollama_chat_android
cd ollama_chat_android

# 4. Dependencias necesarias (pubspec.yaml)
# http: ^1.2.0       ← Peticiones HTTP con streaming
# provider: ^6.1.1   ← Gestión de estado
# sqflite: ^2.3.0    ← Base de datos local para historial
# shared_preferences ← Guardar configuración
``` 
Interfaz de evaluación de modelos de IA local mediante Ollama + generación de
informes de inteligencia OSINT.

---

*Última actualización: Agosto 2026*