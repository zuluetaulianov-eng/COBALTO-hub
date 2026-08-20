# 🛰️ COBALTO HUB — MANUAL COMPLETO DE TEATROS OPERACIONALES: COLOMBIA & VENEZUELA

**Sistema de Mando y Control de Inteligencia (C4I) — Arquitectura Multi-Teatro v13.0 / v14.0**

Este documento proporciona el desglose técnico, operativo y la configuración detallada de los vectores de inteligencia de **Colombia** y **Venezuela**, incluyendo entidades, palabras clave, dominios, medios de comunicación, canales de extracción y sensores geoespaciales integrados en el sistema.

---

## 📌 1. Visión General de la Arquitectura Multi-Teatro

El motor **Multi-Theater OSINT** de COBALTO HUB opera mediante una arquitectura modular basada en archivos JSON (`data/theaters/*.json`) y gestionada por `theaters_config.py`. 

### Principios Fundamentales:
1. **Ingesta Políglota y Multicanal**: Captura noticias RSS, posts de Telegram, tweets/perfiles sociales, sismos y telemetría BFT.
2. **Auto-Clasificación por Teatro**: Cada elemento extraído es analizado en tiempo real por `detect_country_tags()`, asignándole etiquetas regionales (`COL`, `VEN`, `GLOBAL`).
3. **Expedientes Tácticos 360°**: Consolidación automática de personas e instituciones clave mediante `dossier_engine.py`.
4. **Auto-Alimentación Continua**: Cosecha diaria de palabras clave emergentes vía `keyword_harvester.py` y seguimiento automático con `auto_tracker.py`.

---

## 🇨🇴 2. TEATRO OPERACIONAL 1: COLOMBIA (`COL`)

### 📋 Resumen Operativo
- **Código de Teatro**: `COL`
- **Icono / Bandera**: 🇨🇴
- **Foco de Inteligencia**: Monitoreo del conflicto armado interno, transición política, crimen organizado transnacional, paz total y seguridad fronteriza.
- **Centro Geoespacial**: Latitud `6.5`, Longitud `-70.0` (Zoom predeterminado: `5`).

---

### 🏢 2.1 Instituciones y Objetivos Tácticos de Interés (`target_users` / `institutions`)

#### Figuras Políticas e Instituciones Clave:
- **Abelardo de la Espriella (ADLE)**
- **Gustavo Petro** (Presidencia de la República)
- **Iván Cepeda**
- **Presidencia de la República de Colombia** (Casa de Nariño)
- **Ministerio de Defensa Colombia** (FFMM, Cantón Militar Pichincha, GAULA)
- **Ministerio del Interior Colombia**
- **Congreso de la República de Colombia**
- **Fiscalía General de la Nación**
- **Defensoría del Pueblo de Colombia** (`DefensoriaCol`)

#### Cuentas y Censores OSINT Monitoreados:
| Usuario / Handle | Nombre / Organización | Enfoque Táctico |
|---|---|---|
| `@ArielAvilaAnaliza` | Ariel Ávila | Análisis de conflicto y política |
| `@LeonVaLenciaA` | León Valencia | Fundación Paz & Reconciliación (Pares) |
| `@FIP_Col` | Fundación Ideas para la Paz | Dinámicas de violencia y conflicto |
| `@Indepaz` | INDEPAZ | Masacres, líderes sociales, pactos |
| `@DanielMejiaL` | Daniel Mejía | Seguridad urbana y criminología |
| `@lasillavacia` | La Silla Vacía | Redes de poder y política |
| `@DefensoriaCol` | Defensoría del Pueblo | Alertas tempranas de riesgo de DDHH |

---

### 🔑 2.2 Set Completo de Palabras Clave y Términos de Vigilancia (`keywords`)

Las entradas que contengan cualquiera de estos términos se clasifican y etiquetan automáticamente dentro del teatro **Colombia**:

```text
colombia, bogotá, bogota, medellín, medellin, cali, cauca, catatumbo, arauca,
tumaco, putumayo, chocó, eln, emc, marquetalia, clan del golfo, gaitanistas,
petro, caño limón, paz total, gaula, ffmm colombia, abelardo de la espriella,
adle, presidencia de la república, ministerio de defensa colombia, ministerio del interior,
iván cepeda, casa de nariño, cantón militar pichincha, congreso de la república,
fiscalía general de la nación
```

---

### 🌐 2.3 Medios de Comunicación, Portales y Canales de Extracción (`domains`)

El sistema monitorea y extrae contenidos de forma continua a través de 16 medios colombianos abiertos y especializados:

| Portal / Medio | Dominio | Tipo de Fuente |
|---|---|---|
| **Noticias RCN** | `noticiasrcn.com` | Medio masivo / TV |
| **Noticias Caracol** | `noticias.caracoltv.com` | Medio masivo / TV |
| **Semana** | `semana.com` | Revista / Investigación |
| **El Tiempo** | `eltiempo.com` | Prensa nacional |
| **El Espectador** | `elespectador.com` | Prensa nacional |
| **La FM** | `lafm.com.co` | Radio / Noticias |
| **Blu Radio** | `bluradio.com` | Radio / Noticias |
| **Cambio Colombia** | `cambiocolombia.com` | Periodismo de investigación |
| **La Silla Vacía** | `lasillavacia.com` | Análisis político |
| **Verdad Abierta** | `verdadabierta.com` | Conflicto armado y DDHH |
| **Fundación Pares** | `pares.com.co` | Paz & Reconciliación |
| **Vanguardia** | `vanguardia.com` | Prensa regional (Santanderes) |
| **El Colombiano** | `elcolombiano.com` | Prensa regional (Antioquia) |
| **El País (Cali)** | `elpais.com.co` | Prensa regional (Valle del Cauca) |
| **El Heraldo** | `elheraldo.co` | Prensa regional (Caribe) |
| **France 24 (Colombia)** | `france24.com` | Cobertura internacional dedicada |

---

### 📍 2.4 Geocerca Sísmica y Sensor Geoespacial (`seismic_geofence`)

- **Latitud Central**: `4.7110` (Bogotá)
- **Longitud Central**: `-74.0721`
- **Radio de Cobertura**: `600 km`
- **Función**: Filtra en tiempo real los eventos telúricos reportados por el USGS que impacten el territorio colombiano o zonas fronterizas.

---

## 🇻🇪 3. TEATRO OPERACIONAL 2: VENEZUELA (`VEN`)

### 📋 Resumen Operativo
- **Código de Teatro**: `VEN`
- **Icono / Bandera**: 🇻🇪
- **Foco de Inteligencia**: Vigilancia de seguridad nacional, dinámica político-militar (FANB/CEOFANB), cibernética, servicios públicos/infraestructura y frontera binacional.
- **Centro Geoespacial**: Latitud `7.5`, Longitud `-66.5` (Zoom predeterminado: `6`).

---

### 🏢 3.1 Instituciones y Objetivos Tácticos de Interés (`target_users` / `institutions`)

#### Figuras Políticas e Instituciones Clave:
- **Nicolás Maduro** (Presidencia de la República)
- **Vladimir Padrino López** (Ministerio del Poder Popular para la Defensa)
- **Diosdado Cabello** (MPPRIJP)
- **CEOFANB / Prensa FANB**
- **SEBIN / DGCIM**
- **CANTV** (Telecomunicaciones e infraestructura)
- **CICPC** (Cuerpo de Investigaciones Científicas, Penales y Criminalísticas)

#### Cuentas y Censores OSINT Monitoreados:
| Usuario / Handle | Nombre / Organización | Enfoque Táctico |
|---|---|---|
| `@PresidencialVen` | Prensa Presidencial | Declaraciones oficiales del Ejecutivo |
| `@PrensaFANB` | Prensa FANB | Despliegues militares y operaciones |
| `@REDI_Capital` | REDI Capital | Defensa de la región capital |
| `@DouglasRicoVzla` | Douglas Rico (CICPC) | Reportes de seguridad y delincuencia |

---

### 🔑 3.2 Set Completo de Palabras Clave y Términos de Vigilancia (`keywords`)

Las entradas que contengan cualquiera de estos términos se clasifican automáticamente dentro del teatro **Venezuela**:

```text
venezuela, caracas, maracaibo, valencia, barquisimeto, zulia, tachira, fanb,
padrino lópez, maduro, diosdado, cantv, sebin, ceofanb, dgcip, cicpc,
redes de servicios, mpprijp, vencert
```

---

### 🌐 3.3 Medios de Comunicación, Portales y Canales de Extracción (`domains`)

El sistema monitorea 8 portales independientes y fuentes oficiales de ciberseguridad en Venezuela:

| Portal / Medio | Dominio | Tipo de Fuente |
|---|---|---|
| **El Pitazo** | `elpitazo.net` | Noticias y servicios públicos |
| **Runrunes** | `runrun.es` | Periodismo de investigación |
| **La Patilla** | `lapatilla.com` | Monitoreo de noticias en vivo |
| **Efecto Cocuyo** | `efectococuyo.com` | Verificación y política |
| **Tal Cual Digital** | `talcualdigital.com` | Prensa independiente |
| **El Diario** | `eldiario.com` | Reportajes y economía |
| **VenCERT** | `vencert.gob.ve` | Ciberseguridad e incidentes CERT |
| **MPPRIJP** | `mpprijp.gob.ve` | Ministerio de Interiores y Justicia |

---

### 📍 3.4 Geocerca Sísmica y Sensor Geoespacial (`seismic_geofence`)

- **Latitud Central**: `10.4806` (Caracas)
- **Longitud Central**: `-66.9036`
- **Radio de Cobertura**: `400 km`
- **Función**: Detecta sismos y perturbaciones telúricas en la franja costera y norte de Venezuela.

---

## 🌐 4. VECTOR INTERNACIONAL Y TRANSNACIONAL (`GLOBAL`)

Para abarcar el crimen transnacional y las agencias multilaterales que reportan sobre Colombia y Venezuela, COBALTO HUB mantiene el teatro **GLOBAL**:

- **Medios Clave**: `insightcrime.org` (Insight Crime en español), `reuters.com`, `bbc.com`, `apnews.com`, `dw.com`, `france24.com`.
- **Cuentas Objetivo**: `@InSightCrime`, `@UN_Spokesperson`.
- **Zonas Fronterizas de Cruce Transnacional**:
  - *Eje Arauca ↔ Apure*: Monitoreo de grupos armados (ELN, EMC, Frente 10).
  - *Eje Zulia ↔ Norte de Santander*: Monitoreo de contrabando, narcotráfico y pasos irregulares.

---

## ⚙️ 5. Funcionamiento Interno del Motor Multi-Teatro

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXTRACTORES (RSS, TELEGRAM, OSINT)                       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   AUTO-TAGGING (theaters_config.py)                         │
│   Evalúa texto, dominio y fuentes -> Asigna ["COL"], ["VEN"] o ["GLOBAL"]    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                AUTO-ALIMENTACIÓN (keyword_harvester.py)                      │
│   Cosecha hashtags y n-gramas de alta frecuencia -> auto_tracker.py         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 EXPEDIENTES 360° (dossier_engine.py)                         │
│   Calcula Risk Score (0-10), Presión Mediática y Línea de Tiempo             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       INTERFAZ Y FILTRADO (UI)                              │
│   Selector en Sidebar -> switchTheater('COL'|'VEN'|'GLOBAL')                 │
│   Filtrado DOM + Vuelo de Mapa (flyTo) instantáneo                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔑 6. Puntos Claves de Operación y Escalado

1. **Selección Instantánea en Sidebar**:
   - En la barra lateral (`_sidebar.html`), el operador puede cambiar de teatro (`🇨🇴 Colombia`, `🇻🇪 Venezuela`, `🌐 Global`).
   - La función `switchTheater()` filtra las tarjetas de noticias en tiempo real mediante el atributo `data-country` y desplaza la vista del mapa Leaflet a las coordenadas centrales del país seleccionado.

2. **Cosecha de Términos Emergentes**:
   - El worker ejecuta `keyword_harvester.py` al final de cada ciclo, identificando automáticamente hashtags y temas candentes en Colombia y Venezuela.
   - El módulo `auto_tracker.py` auto-ingresa los términos de mayor aceleración en la lista activa de monitoreo.

3. **Expedientes Tácticos Integrados**:
   - Al buscar o seleccionar una persona o institución (ej. *Ministerio de Defensa Colombia* o *Padrino López*), el botón **`📜 VER DOSSIER TÁCTICO 360°`** consulta el backend `/api/dossier` para entregar un reporte holístico de menciones, nivel de riesgo y sucesos recientes.

4. **Escalabilidad Modular**:
   - Para añadir un nuevo país (ej. Ecuador `ECU` o Brasil `BRA`), basta con crear un archivo `data/theaters/ecuador.json` siguiendo la estructura estándar. No requiere modificar el código fuente principal.
