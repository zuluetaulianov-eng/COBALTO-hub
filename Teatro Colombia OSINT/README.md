# 🇨🇴 TEATRO COLOMBIA OSINT — EXTRACTOR E INFRAESTRUCTURA DE INTELIGENCIA

Este directorio contiene la suite completa y desacoplada de extracción de inteligencia para el **Teatro Colombia (`COL`)**. Puede ser ejecutada de forma independiente o integrada en cualquier microservicio / backend de análisis táctico.

---

## 📦 Contenido del Paquete

| Archivo | Descripción |
|---|---|
| `osiris_colombia_recon.py` | Motor de extracción principal (SECOP II via Socrata SoQL, JEP Sala de Prensa, Rama Judicial stealth XHR & SQLite local). |
| `seed_colombia_entities.py` | Diccionario y sembrado de entidades tácticas (Grupos Armados, Líderes, Mandatarios, Infraestructura). |
| `README_FUENTES_COLOMBIA.md` | Manual exhaustivo de fuentes, medios, geocercas y palabras clave monitoreadas. |
| `test_colombia_recon.py` | Suite de pruebas unitarias y de integración en pytest. |

---

## 🛠️ Requisitos de Instalación

```bash
pip install aiohttp beautifulsoup4 pytest
```

---

## 🚀 Uso Rápido (Standalone)

### 1. Ejecutar Extracción Masiva de SECOP II (Datos Abiertos)

```python
import asyncio
from osiris_colombia_recon import query_secop_socrata

async def main():
    # Consulta de contratos de defensa en Antioquia
    contratos = await query_secop_socrata(
        query_text="vigilancia",
        departamento="Antioquia",
        limit=50
    )
    print(f"Contratos extraídos: {len(contratos)}")

asyncio.run(main())
```

### 2. Consultar Expediente Judicial en la Rama Judicial (23 dígitos)

```python
import asyncio
from osiris_colombia_recon import query_rama_judicial_radicado

async def main():
    proceso = await query_rama_judicial_radicado("05001310400120220012300")
    print(proceso)

asyncio.run(main())
```

### 3. Sembrado de Entidades Tácticas

```bash
python seed_colombia_entities.py
```

### 4. Ejecutar Suite de Pruebas

```bash
pytest test_colombia_recon.py -v
```

---

*Desarrollado para la Plataforma de Inteligencia y Mando C4I COBALTO Hub.*
