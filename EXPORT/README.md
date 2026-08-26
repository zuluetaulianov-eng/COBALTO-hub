# 🧠 Módulo Autónomo de Inteligencia Artificial y Generación de Reportes

Este directorio contiene la arquitectura completa, modular y autosuficiente de inferencia con Inteligencia Artificial extraída del ecosistema **COBALTO Hub**. Diseñado para integrarse en cualquier proyecto de Python (FastAPI, Flask, Django, bots o scripts CLI), este módulo proporciona una capa resiliente sobre **CometAPI** (compatible con OpenAI API), **NVIDIA API** e **IA Local (Ollama)**.

---

## 🏗️ Estructura del Proyecto Exportado

```
EXPORT/
├── .env                  # Credenciales de API (CometAPI Keys 1..5, Base URL, Modelos)
├── ai_engine.py          # Motor central de inferencia, Pool de rotación y Circuit Breaker
├── report_generator.py   # Orquestador de análisis táctico, SITREPs JSON y debates multi-agente
├── example_usage.py      # Script de prueba listo para ejecución directa
└── README.md             # Documentación técnica completa y guía de integración
```

---

## 📊 Arquitectura del Sistema

```mermaid
graph TD
    A[Cliente / Aplicación Externa] --> B[report_generator.py]
    B --> C[ai_engine.py: ask_ai()]
    C --> D{Disyuntor Circuit Breaker}
    D -- Abierto (En Pausa) --> E[Espera / Retorno Fallback]
    D -- Cerrado (Saludable) --> F[Pool Rotativo de API Keys]
    F --> G1[CometAPI Key 1]
    F --> G2[CometAPI Key 2]
    F --> G3[CometAPI Key 3]
    F --> G4[CometAPI Key 4]
    F --> G5[CometAPI Key 5]
    G1 --> H[CometAPI Endpoint: https://api.cometapi.com/v1]
    G2 --> H
    G3 --> H
    G4 --> H
    G5 --> H
    H -- Fallo / Rate Limit 429 --> I[Fallback a Modelo gpt-4o-mini]
    H -- Éxito 200 --> J[JSON / Respuesta Formateada]
```

---

## 🛡️ Mecanismos de Alta Disponibilidad y Resiliencia

1. **Rotación Round-Robin de API Keys**:
   - `get_ai_pool()` instancia clientes `AsyncOpenAI` para cada clave configurada en el `.env`.
   - Prioriza las llaves con prefijo `sk-` (CometAPI) para mantener compatibilidad nativa con modelos de OpenAI (`gpt-4o`, `gpt-4o-mini`).
   - Mantiene un contador de fallos consecutivos por clave (mediante hash MD5 de la API Key). Si una clave falla más de 3 veces, es omitida temporalmente.

2. **Patrón Disyuntor (Circuit Breaker)**:
   - Administra el estado global de disponibilidad del pool de IA: `CLOSED` (normal), `OPEN` (bloqueado por fallos masivos) y `HALF-OPEN` (prueba de recuperación tras tiempo de enfriamiento).

3. **Inferencia Adaptativa con Fallback Transparente**:
   - `ask_ai(...)` maneja reintentos exponenciales con jitter aleatorio.
   - Si el modelo principal (`gpt-4o`) devuelve error de cuota o precio, conmuta automáticamente a `gpt-4o-mini` sin interrumpir el flujo.

---

## ⚙️ Configuración (`.env`)

```env
# CometAPI (Servicio Principal OpenAI Compatible)
COMETAPI_BASE_URL=https://api.cometapi.com/v1
COMETAPI_KEY_1=sk-th15OZfyVBpeZOaWDDHrjOYcRp2yEIzrbwnVx4vit97Des1c
COMETAPI_KEY_2=sk-OxXIUy9aWAXYqPOpXwrc8M8jQpsRJZjOlTiUg0w5acFol5wn
COMETAPI_KEY_3=sk-C2dpPLWNF0rRR5qwUxQYbD0HoZDfTo8RJ1uT3g7bBs2ywn15
COMETAPI_KEY_4=sk-MJ0oHKHA9CIwXj7IH0zmbphTcDSAM2KnNAlWPlepYweEfU7M
COMETAPI_KEY_5=sk-OXs2rt1mjUuLS5iD1Bv66tm6jAvDXsRiRt1Ux0IV3owTmvYV

# Modelo por defecto
AI_MODEL=gpt-4o

# NVIDIA / Groq (Respaldo Opcional)
GROQ_API_KEY=nvapi-...
GROQ_API_KEY_COORD=nvapi-...

# IA Local (Ollama - Opcional)
OLLAMA_ENABLED=false
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

---

## 📖 Referencia de Código y Funciones

### 1. `ai_engine.py` (Motor de Inferencia Base)

#### `ask_ai(prompt, system_prompt, model, json_mode, temperature, max_tokens, max_retries)`
Ejecuta consultas asíncronas a la IA gestionando reintentos y rotación de claves.
- **Parámetros**:
  - `prompt` (*str*): Texto o consulta del usuario.
  - `system_prompt` (*str*): Instrucción de rol o contexto.
  - `model` (*Optional[str]*): Modelo objetivo (defecto: `gpt-4o`).
  - `json_mode` (*bool*): Si es `True`, fuerza la respuesta en formato JSON estructurado.
  - `temperature` (*float*): Creatividad (0.0 a 1.0).
  - `max_tokens` (*int*): Límite de tokens de respuesta.
- **Retorno**: `Optional[str]` con la respuesta generada o `None` en caso de error no recuperable.

---

### 2. `report_generator.py` (Generador de Reportes)

#### `generar_informe_sitrep(titulo, contenido, fuente)`
Analiza un evento o noticia y produce una evaluación táctica estructurada en JSON.
- **Retorno Dict**:
  ```json
  {
    "actores": ["actor1", "actor2"],
    "nivel_amenaza": "CRÍTICA | ALTA | MEDIA | BAJA",
    "resumen_ejecutivo": "Descripción en 2-3 oraciones",
    "recomendaciones": ["acción 1", "acción 2"]
  }
  ```

#### `generar_informe_masivo(entradas, limite_concurrencia)`
Procesa listas de noticias en paralelo utilizando un semáforo asíncrono para no saturar las tasas de API.

#### `generar_debate_multiagente(noticias)`
Simula un debate entre 3 perfiles analíticos especializados (Táctico, Geopolítico, Ciberseguridad) y compila un consenso ejecutivo unificado.

---

## 🚀 Guía de Integración en un Proyecto Nuevo

1. **Copiar la carpeta `EXPORT`** a tu proyecto.
2. **Instalar dependencias**:
   ```bash
   pip install openai python-dotenv aiohttp
   ```
3. **Importar y Usar**:
   ```python
   import asyncio
   from ai_engine import ask_ai
   from report_generator import generar_informe_sitrep

   async def main():
       # Ejemplo 1: Consulta directa
       res = await ask_ai("Resume la importancia de la ciberseguridad en 1 frase.")
       print("Respuesta:", res)

       # Ejemplo 2: Generar reporte JSON
       reporte = await generar_informe_sitrep(
           titulo="Alerta de Intrusión en Red",
           contenido="Se detectó tráfico anómalo en el puerto 8080 originado por una IP externa.",
           fuente="SIEM Sensor"
       )
       print("Nivel de amenaza:", reporte.get("nivel_amenaza"))
       print("Recomendaciones:", reporte.get("recomendaciones"))

   if __name__ == "__main__":
       asyncio.run(main())
   ```

---

## 🧪 Verificación Rápida

Ejecuta el script de prueba incluido para validar que la conexión con CometAPI y el formateo de reportes estén operativos:

```bash
python EXPORT/example_usage.py
```
