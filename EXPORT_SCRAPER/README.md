# 🕷️ Módulo Autónomo de Scrapers OSINT y Redes Sociales (EXPORT_SCRAPER)

Este directorio contiene los **5 módulos de scraping independientes** extraídos de **COBALTO Hub**, diseñados para la recolección de datos en fuentes públicas, redes federadas, comunidades técnicas y la Dark Web **sin requerir APIs pagas ni tokens de sesión obligatorios**.

---

## 📁 Archivos Incluidos

```
EXPORT_SCRAPER/
├── hacker_news_scraper.py   # Extractor para Hacker News (HNRSS y Algolia HN REST API)
├── darkweb_paste_scraper.py # Scraper de sitios de leaks/paste y soporte Tor SOCKS5 para .onion
├── linkedin_scraper.py      # Extractor de perfiles y empresas en LinkedIn vía OSINT dorking
├── mastodon_scraper.py      # Extractor federado de Mastodon (multi-instancia sin auth)
├── bluesky_scraper.py       # Extractor de Bluesky vía AT Protocol Public REST API
├── example_usage.py         # Script ejecutable de demostración
└── README.md                # Documentación técnica completa
```

---

## 🛠️ Funcionamiento Técnico de Cada Scraper

### 1. 🟠 Hacker News (`hacker_news_scraper.py`)
- **Funcionamiento**: Combina la API pública de búsqueda de Algolia (`hn.algolia.com/api/v1/search_by_date`) y los feeds HNRSS (`hnrss.org/frontpage`).
- **Capacidades**: Búsqueda por palabras clave (`query`), filtro por tipo (`story`, `comment`), conteo de puntos y comentarios.
- **Requiere API Key**: ❌ No.

### 2. 🧅 Dark Web & Paste Sites (`darkweb_paste_scraper.py`)
- **Funcionamiento**: Monitorea repositorios de filtraciones públicas (`psbdmp.ws`) y scraping de enlaces `.onion` a través de proxy SOCKS5 de Tor (`127.0.0.1:9050`/`9150`).
- **Capacidades**: Extracción sintáctica de billeteras de criptomonedas (BTC, ETH, TRON, SOL, XMR), detección de leaks de credenciales y palabras clave de sanciones (OFAC / SDN).
- **Requiere Tor**: 🟢 Opcional para sitios `.onion` (requiere servicio de Tor en puerto 9050 o 9150).

### 3. 💼 LinkedIn (`linkedin_scraper.py`)
- **Funcionamiento**: Realiza OSINT Dorking refinado (`site:linkedin.com/in/` o `site:linkedin.com/company/`) sobre motores de búsqueda ligeros (DuckDuckGo Lite) evitando bloqueos y captchas.
- **Capacidades**: Obtención de nombres, cargos, nombres de usuario e instituciones corporativas sin requerir inicio de sesión.
- **Requiere API Key**: ❌ No.

### 4. 🐘 Mastodon (`mastodon_scraper.py`)
- **Funcionamiento**: Consulta en paralelo múltiples instancias federadas (`mastodon.social`, `fosstodon.org`, `infosec.exchange`) mediante su API REST abierta `/api/v1/timelines/tag/{hashtag}`.
- **Capacidades**: Obtención de publicaciones en tiempo real, limpieza de HTML, adjuntos multimedia y metadatos de autor.
- **Requiere API Key**: ❌ No.

### 5. 🦋 Bluesky (`bluesky_scraper.py`)
- **Funcionamiento**: Utiliza el protocolo abierto AT Protocol mediante los endpoints públicos de la API de Bluesky (`public.api.bsky.app/xrpc/app.bsky.feed.searchPosts`).
- **Capacidades**: Búsqueda de posts por hashtag o término libre, consulta de perfiles (`app.bsky.actor.getProfile`), métricas de likes y reposts.
- **Requiere API Key**: ❌ No.

---

## 🚀 Requisitos e Instalación

Instala las librerías necesarias en tu proyecto destino:

```bash
pip install aiohttp feedparser beautifulsoup4
```

*Nota: Para habilitar el scraping de sitios `.onion` en `darkweb_paste_scraper.py`, instala opcionalmente `aiohttp[speedups]` y `pysocks`.*

```bash
pip install aiohttp[speedups] PySocks
```

---

## 💻 Ejemplos de Uso Rápido

### Ejemplo 1: Consultar publicaciones en Bluesky y Mastodon (Asíncrono)

```python
import asyncio
from bluesky_scraper import fetch_bluesky_posts
from mastodon_scraper import fetch_mastodon_hashtag

async def main():
    # Bluesky
    posts_bsky = await fetch_bluesky_posts("ciberseguridad", limit=5)
    print("Bluesky:", len(posts_bsky))

    # Mastodon
    posts_masto = await fetch_mastodon_hashtag("infosec", max_items=5)
    print("Mastodon:", len(posts_masto))

asyncio.run(main())
```

### Ejemplo 2: Analizar texto de filtraciones en Dark Web (Síncrono)

```python
from darkweb_paste_scraper import analyze_leak_text

texto_analisis = "Base de datos filtrada. Admin BTC: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa password: MyPassword123"
analisis = analyze_leak_text(texto_analisis)

print("Billeteras encontradas:", analisis["crypto_wallets"])
print("Indicadores de amenaza:", analisis["threat_indicators"])
```

---

## 🧪 Verificación Rápida

Ejecuta el script de prueba de los 5 scrapers en tu terminal:

```bash
python EXPORT_SCRAPER/example_usage.py
```
