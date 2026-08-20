# config.py - Configuración centralizada v7.0.11 – Hardening 2026 corregido
import json
import logging
import os
from urllib.parse import urlparse

# Feeds verificados (marzo 2026), duplicados eliminados, sintaxis fija, compatibilidad total

__version__ = "7.0.11"
LAST_UPDATED = "2026-05-14"

# ────────────────────────────────────────────────
# Fuentes RSS – solo feeds activos y relevantes al 2026
# ────────────────────────────────────────────────

RSS_FEEDS = {
    # Venezuela - Tradicional/Independiente
    "El Nacional": "https://www.elnacional.com/feed/",
    "El Estímulo": "https://elestimulo.com/feed/",
    "El Diario": "https://eldiario.com/feed/",
    "Runrun.es": "https://runrun.es/feed/",
    "Efecto Cocuyo": "https://efectococuyo.com/feed/",
    "Caracas Chronicles": "https://www.caracaschronicles.com/feed/",
    "EVTV Miami": "https://evtv.online/feed/",
    "El Pitazo": "https://elpitazo.net/feed/",
    "Crónica Uno": "https://cronica.uno/feed/",
    "Últimas Noticias": "https://ultimasnoticias.com.ve/feed/",
    "2001 Online": "https://2001online.com/feed/",
    "El Impulso": "https://www.elimpulso.com/feed/",
    "El Carabobeño": "https://www.el-carabobeno.com/feed/",
    "La Patilla": "https://www.lapatilla.com/feed/",
    "Alnavío": "https://alnavio.com/feed/",
    "Undercode News": "https://undercodenews.com/feed/",
    "Descifrado": "https://www.descifrado.com/feed/",
    # Venezuela - Estatales/Oficiales
    "teleSUR": "https://www.telesurtv.net/rss/",
    # "AVN": "https://www.avn.info.ve/rss", # Desactivado: RSS roto (retorna HTML)
    "VTV Canal 8": "https://vtv.com.ve/feed/",
    # Venezuela - CERT/SUSCERTE Gobierno
    "VenCERT Alertas": "https://vencert.suscerte.gob.ve/category/alertas/feed/",
    "VenCERT Boletines": "https://vencert.suscerte.gob.ve/category/boletines/feed/",
    "VenCERT General": "https://vencert.suscerte.gob.ve/feed/",
    # Económicas/Especializadas
    "Banca y Negocios": "https://www.bancaynegocios.com/feed/",
    "Finanzas Digital": "https://finanzasdigital.com/feed/",
    "DolarToday": "https://dolartoday.com/feed/",
    # Internacional - Neutral
    "BBC Mundo": "https://feeds.bbci.co.uk/mundo/rss.xml",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Voz de América": "https://www.vozdeamerica.com/api/zvirqol-vomx-tpeugoqi",
    "CNN en Español": "http://rss.cnn.com/rss/edition_americas.rss",
    "El País": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/america/portada",
    "The Guardian World": "https://www.theguardian.com/world/rss",
    "Al Jazeera English": "https://www.aljazeera.com/xml/rss/all.xml",
    "France 24 Latinoamérica": "https://www.france24.com/es/am%C3%A9rica-latina/rss",
    # Análisis/Investigación
    "Insight Crime": "https://insightcrime.org/feed/",
    "Bellingcat": "https://www.bellingcat.com/feed/",
    # Derechos Humanos
    # Ciberseguridad
    "Krebs on Security": "https://krebsonsecurity.com/feed/",
    "Schneier on Security": "https://www.schneier.com/feed/",
    "Malwarebytes Labs": "https://www.malwarebytes.com/blog/feed",
    "SANS Internet Storm Center": "https://isc.sans.edu/rssfeed.xml",
    # Tech/IA
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "Google Research Blog": "https://research.google/blog/rss/",
    "Real Python": "https://realpython.com/atom.xml",
    "LWN.net": "https://lwn.net/headlines/rss",
    "Hacker News": "https://hnrss.org/frontpage",
    "Phoronix": "https://www.phoronix.com/rss.php",
    # Regional
    "Kaieteur News (Guyana)": "https://kaieteurnewsonline.com/feed/",
    "Guyana Chronicle": "https://guyanachronicle.com/feed/",
    "Caribbean News Global": "https://caribbeannewsglobal.com/feed/",
    "Jamaica Gleaner": "https://jamaica-gleaner.com/feed/news.xml",
    "O Globo (Brasil)": "https://oglobo.globo.com/rss/oglobo",
    # Colombia - Medios Nacionales y de Investigación
    "El Tiempo (Colombia)": "https://www.eltiempo.com/rss/colombia.xml",
    "El Espectador": "https://www.elespectador.com/arc/outboundfeeds/rss/",
    "Revista Semana": "https://www.semana.com/arc/outboundfeeds/rss/",
    "Caracol Radio": "https://caracol.com.co/rss/",
    "RCN Radio": "https://www.rcnradio.com/rss",
    "Noticias Caracol": "https://noticias.caracoltv.com/rss.xml",
    "La Silla Vacía": "https://www.lasillavacia.com/feed/",
    "La República": "https://www.larepublica.co/rss",
    "Portafolio": "https://www.portafolio.co/rss",
    "La Opinión (Cúcuta)": "https://www.laopinion.com.co/rss.xml",
    "El Heraldo": "https://www.elheraldo.co/rss.xml",
    "El Colombiano": "https://www.elcolombiano.com/rss",
    "Cuestión Pública": "https://cuestionpublica.com/feed/",
    "W Radio Colombia": "https://www.wradio.com.co/rss/",
    "Vanguardia Liberal": "https://www.vanguardia.com/rss/colombia.xml",
    "El País (Cali)": "https://www.elpais.com.co/rss",
    "La FM": "https://www.lafm.com.co/rss",
    "Blu Radio": "https://www.bluradio.com/rss",
    "Cambio Colombia": "https://cambiocolombia.com/feed/",
    "Verdad Abierta": "https://verdadabierta.com/feed/",
    "Fundación Pares": "https://pares.com.co/feed/",
    "France 24 Colombia": "https://www.france24.com/es/am%C3%A9rica-latina/colombia/rss",
    # Tech en Español
    "Apuntes de Seguridad": "https://www.apuntesdeseguridad.com/feed/",
}

# ── Fuentes Telegram (NO son RSS - requieren scraper especial) ──
TELEGRAM_SOURCES = {
    # Venezuela
    "Venevisión Oficial": "https://t.me/s/noticierovenevision",
    "El Pitazo Venezuela": "https://t.me/s/elpitazove",
    "La Patilla Canal": "https://t.me/s/lapatillaoficial",
    "Efecto Cocuyo": "https://t.me/s/efectococuyo",
    "AlbertoRodNews (Venezuela)": "https://t.me/s/AlbertoRodNews",
    "RunRunes": "https://t.me/s/runrunesweb",
    # Colombia
    "Noticias Caracol": "https://t.me/s/NoticiasCaracol",
    "El Tiempo Colombia": "https://t.me/s/ElTiempoColombia",
    "Revista Semana": "https://t.me/s/RevistaSemana",
    "Noticias RCN": "https://t.me/s/NoticiasRCN",
    "El Espectador": "https://t.me/s/elespectadorcom",
    "Blu Radio Colombia": "https://t.me/s/bluradioco",
}

# ── Fuentes Prioritarias (para carga rápida inicial) ──
PRIORITY_FEEDS = [
    "El Nacional",
    "El Estímulo",
    "Runrun.es",
    "Efecto Cocuyo",
    "BBC Mundo",
    "Voz de América",
    "CNN en Español",
    "El País",
    "La Patilla",
    "Alnavío",
    "Undercode News",
    # Nota: Banca y Negocios, DolarToday y VenCERT se removieron de PRIORITY por fallos
    # persistentes de conectividad. Siguen en RSS_FEEDS para el ciclo FULL.
]


SOCIAL_FETCH_BATCH_SIZE = 4

# ── Monitoreo Sísmico (USGS + Geocerca) ──
SEISMIC_MONITOR_ENABLED = os.getenv("SEISMIC_MONITOR_ENABLED", "true").lower() == "true"
SEISMIC_TARGET_LAT = float(os.getenv("SEISMIC_TARGET_LAT", "10.4806"))
SEISMIC_TARGET_LON = float(os.getenv("SEISMIC_TARGET_LON", "-66.9036"))
SEISMIC_MAX_DISTANCE_KM = float(os.getenv("SEISMIC_MAX_DISTANCE_KM", "400"))
SEISMIC_MIN_MAGNITUDE = float(os.getenv("SEISMIC_MIN_MAGNITUDE", "3.5"))

# ── Monitoreo ASN (IODA: apagones de internet en infraestructura crítica) ──
ASN_MONITOR_ENABLED = os.getenv("ASN_MONITOR_ENABLED", "true").lower() == "true"
ASN_DROP_THRESHOLD = float(os.getenv("ASN_DROP_THRESHOLD", "30"))

# ── Monitoreo GDACS (Alertas ONU: ciclones, inundaciones, incendios, volcanes) ──
GDACS_MONITOR_ENABLED = os.getenv("GDACS_MONITOR_ENABLED", "true").lower() == "true"
GDACS_MAX_DISTANCE_KM = float(os.getenv("GDACS_MAX_DISTANCE_KM", "800"))
GDACS_EVENT_DAYS = int(os.getenv("GDACS_EVENT_DAYS", "2"))

# ── Control de Ciclos y Caché ──
CACHE_MAX_AGE_MINUTES = int(os.getenv("CACHE_MAX_AGE_MINUTES", "15"))
ENTRY_MAX_AGE_HOURS = int(os.getenv("ENTRY_MAX_AGE_HOURS", "48"))
CYCLE_INTERVAL_MINUTES = int(os.getenv("CYCLE_INTERVAL_MINUTES", "30"))

# ── Parámetros Operativos C4I ──
DEFCON_LEVEL = int(os.getenv("DEFCON_LEVEL", "3"))
DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "15"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
MODULE_OSINT_ACTIVE = os.getenv("MODULE_OSINT_ACTIVE", "true").lower() == "true"
MODULE_SOCIAL_ACTIVE = os.getenv("MODULE_SOCIAL_ACTIVE", "true").lower() == "true"
MODULE_NLP_ACTIVE = os.getenv("MODULE_NLP_ACTIVE", "true").lower() == "true"

# ── Configuración de Seguridad y Proxies ──
SSL_VERIFY = os.getenv("SSL_VERIFY", "true").lower() == "true"
RESIDENTIAL_PROXY_URL = os.getenv("RESIDENTIAL_PROXY_URL")
USE_TOR_FALLBACK = os.getenv("USE_TOR_FALLBACK", "true").lower() == "true"
TOR_SOCKS_PORT = int(os.getenv("TOR_SOCKS_PORT", "9150"))
REDLIB_INSTANCES = [
    "https://redlib.catsarch.com",
    "https://redlib.vlink.dev",
    "https://libreddit.privacydev.net",
    "https://redlib.freedit.eu",
    "https://libreddit.oxhead.nl",
]

# ── Configuración Geográfica Regional ──
REGIONAL_BBOX = {"lat_min": -5.0, "lat_max": 18.0, "lon_min": -82.0, "lon_max": -50.0}

# Usuarios de alto perfil y hacktivistas para monitoreo
TARGET_USERS = [
    "VenteVenezuela",
    "PresidencialVen",
    "padrinovladimir",
    "Noticias_Libre",
    "ConflictsW",
    "The_Gordon_F",  # Hacktivista Gordon Freeman
    "TeamHDP",  # Grupo Hacker Team HDP
    "AnonymousVene",  # Anonymous Venezuela
    "CyberHuntersVen",  # Rastreadores cibernéticos locales
    "infopresidencia",  # Presidencia de Colombia
    "FuerzasMilCol",  # Fuerzas Militares de Colombia
    "PoliciaColombia",  # Policía Nacional Colombia
    "mindefensa",  # Ministerio de Defensa Colombia
    "ArielAvilaAnaliza",  # Senador / Analista Conflicto
    "LeonVaLenciaA",  # Dir. Fundación Pares
    "FIP_Col",  # Fundación Ideas para la Paz
    "Indepaz",  # Indepaz Colombia
    "DanielMejiaL",  # Analista Seguridad
    "lasillavacia",  # La Silla Vacía
    "DefensoriaCol",  # Defensoría del Pueblo
]

# ── Feeds con problemas conocidos ──
PROBLEM_FEEDS = {
    "AVN": {
        "reason": "Feed destruido; ahora redirecciona a HTML de la portada",
        "since": "2026-05",
        "status": "inactivo",
        "url_actual": "https://www.avn.info.ve/",
        "notes": "Desactivado para evitar errores BOZO en feedparser",
    },
    "El Nacional": {
        "reason": "Cloudflare agresivo + posible bloqueo por IP no-Venezuela",
        "since": "2025-11",
        "status": "intermitente",
        "notes": "Usar proxy rotativo o headers User-Agent moderno en extractor.py",
    },
    "DolarToday": {
        "reason": "Cloudflare agresivo + congestión",
        "since": "2026-03",
        "status": "lento",
        "timeout": 45,
        "notes": "Requiere mayor tiempo de espera y renderizado Playwright forzado si falla directo",
    },
    "Banca y Negocios": {
        "reason": "Bloqueo por IP y User-Agent",
        "since": "2026-04",
        "status": "intermitente",
        "timeout": 30,
    },
    "Voz de América": {
        "reason": "Endpoint API antiguo (z-qyiv-vtt) ya no funciona; reemplazado con feed de sección Venezuela",
        "since": "2026-05",
        "status": "corregido",
        "url_actual": "https://www.vozdeamerica.com/api/zvirqol-vomx-tpeugoqi",
    },
    "CNN en Español": {
        "reason": "Feed específico de Venezuela caído; reemplazado con CNN Americas RSS genérico",
        "since": "2026-05",
        "status": "corregido",
        "url_actual": "http://rss.cnn.com/rss/edition_americas.rss",
    },
    "El Carabobeño": {
        "reason": "Feed anterior (elcarabobeno.com/feed) devolvía 404; actualizado a el-carabobeno.com/feed",
        "since": "2026-05",
        "status": "corregido",
        "url_actual": "https://www.el-carabobeno.com/feed/",
    },
}

# ── Palabras clave refinadas ──
KEYWORDS = [
    # Colombia / Conflicto / Transición / Seguridad / Cobertura Binacional
    "colombia",
    "cúcuta",
    "arauca",
    "norte de santander",
    "catatumbo",
    "cauca",
    "nariño",
    "chocó",
    "putumayo",
    "guaviare",
    "meta",
    "maicao",
    "tibú",
    "tumaco",
    "san vicente del caguán",
    "bajo cauca",
    "magdalena medio",
    "sur de bolívar",
    "eln",
    "ejército de liberación nacional",
    "calarcá",
    "antonio garcía",
    "estado mayor central",
    "emc",
    "segunda marquetalia",
    "clan del golfo",
    "agc",
    "autodefensas gaitanistas",
    "disidencias farc",
    "farc-ep",
    "comandos de la frontera",
    "los pachencas",
    "frente carlos patiño",
    "frente 33",
    "frente adán izquierdo",
    "paz total",
    "petro",
    "abelardo de la espriella",
    "adle",
    "iván cepeda",
    "josé manuel restrepo",
    "honorio miguel henríquez",
    "cantón militar pichincha",
    "ataque armado",
    "atentado",
    "masacre",
    "combate",
    "enfrentamiento armado",
    "toma guerrillera",
    "secuestro",
    "extorsión",
    "desplazamiento forzado",
    "minas antipersona",
    "artefacto explosivo",
    "hostigamiento armado",
    "asesinato selectivo",
    "líder social asesinado",
    "ataque a oleoducto",
    "incursión armada",
    "confinamiento",
    "mesa de negociación eln",
    "curules de paz",
    "circunscripciones especiales",
    "acuerdo de paz 2016",
    "jep",
    "jurisdicción especial para la paz",
    "ruptura de negociaciones",
    "cese al fuego",
    "listado narcoterroristas",
    "mega cárceles",
    "caño limón",
    "oleoducto",
    "ecopetrol",
    "fedegán",
    "andi",
    "cultivos de coca",
    "erradicación forzada",
    "minería ilegal",
    "organismos de verificación",
    "cicr colombia",
    "defensoría del pueblo",
    "acnur colombia",
    "human rights watch colombia",
    # Venezuela política/economía/sociedad
    "dolar",
    "dólar",
    "oposicion",
    "oposición",
    "inteligencia",
    "transporte",
    "accidentes",
    "Bitcoin",
    "politica",
    "política",
    "elecciones",
    "venezuela",
    "golpe",
    "terrorismo",
    "cne",
    "esequibo",
    "fanb",
    "extranjero",
    "petróleo",
    "pdvsa",
    "maduro",
    "machado",
    "nacional",
    "región",
    "informe",
    "reporte",
    "actualidad",
    "noticia",
    "sueldo",
    "explosion",
    "explosión",
    "hiperinflación",
    "protesta",
    "protestas",
    "muerte",
    "sanciones",
    "eeuu",
    "ee.uu.",
    "rusia",
    "china",
    "crisis",
    "gobierno",
    "frontera",
    "detención",
    "arresto",
    "corrupción",
    "gasolina",
    "escasez",
    "migración",
    "seguridad",
    "tensión",
    "militar",
    "clima",
    "salud",
    "educación",
    "vivienda",
    "justicia",
    "cárcel",
    # Ciberseguridad / OSINT / Hacktivismo
    "ransomware",
    "zero day",
    "zero-day",
    "exploit kit",
    "cve-",
    "vulnerabilidad crítica",
    "phishing",
    "spear phishing",
    "credential stuffing",
    "data breach",
    "filtración",
    "supply chain attack",
    "solarwinds",
    "log4j",
    "log4shell",
    "imsi catcher",
    "stingray",
    "pegasus",
    "spyware",
    "finfisher",
    "osint",
    "geoint",
    "socmint",
    "pentest",
    "red team",
    "blue team",
    "hacker",
    "ataque",
    "defensa",
    "cibercrimen",
    "gordon freeman",
    "hacktivista",
    "anonymous venezuela",
    "team hdp",
    "vencert",
    "suserte",
    "cert venezuela",
    # IA / tech / Futuro
    "llm",
    "large language model",
    "gpt",
    "gemini",
    "llama",
    "mistral",
    "huggingface",
    "fine-tuning",
    "rag",
    "prompt",
    "grok",
    "python",
    "vulnerabilidad",
    "open source",
    "robotics",
    "biotech",
]

# ── Intel propia y Notas informativas — cargadas con validación Pydantic ──

_logger = logging.getLogger("cobalto.config")
_STATIC_INTEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static_intel.json")

try:
    from models.intel_models import load_static_intel as _load_intel
    OWN_POSTS, NOTES_INFORMATIVAS = _load_intel(_STATIC_INTEL_PATH)
except ImportError:
    # Fallback si Pydantic no está disponible (entornos muy mínimos)
    _logger.warning("[INTEL] models.intel_models no disponible. Cargando static_intel sin validación.")
    try:
        with open(_STATIC_INTEL_PATH, "r", encoding="utf-8") as _f:
            _static_data = json.load(_f)
            OWN_POSTS = _static_data.get("OWN_POSTS", [])
            NOTES_INFORMATIVAS = _static_data.get("NOTES_INFORMATIVAS", [])
    except Exception:
        OWN_POSTS = []
        NOTES_INFORMATIVAS = []
except Exception as e:
    _logger.exception(f"[INTEL] Error inesperado cargando static_intel.json: {e}")
    OWN_POSTS = []
    NOTES_INFORMATIVAS = []

# ── Metadatos del dashboard ──
SITE_URL = os.getenv("SITE_URL", "https://commandereliminatedextraction.share.zrok.io")
PAGE_TITLE = "COBALTO HUB | Noticias & Intel Venezuela 2026"
PAGE_DESCRIPTION = "Tablero en tiempo real con intel propia y externa. Canal: t.me/notivenezuelaarma"
TELEGRAM_CHANNEL = "https://t.me/notivenezuelaarma"
LOGO_PATH = "/static/icons/icon-512.png"
LOGO_FALLBACK = "/static/icons/icon-192.png"

# ── Configuración Avanzada de IA y LLM ──
AI_MODEL = "meta/llama-3.3-70b-instruct"
AI_TEMPERATURE = 0.55
AI_MAX_TOKENS = 800

# ── IA Local (Ollama) ──
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "true").lower() == "true"
PREFER_LOCAL_AI = os.getenv("PREFER_LOCAL_AI", "true").lower() == "true"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", "11434"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "180"))
AI_SYSTEM_PROMPT_ARES = "Tu perspectiva es ABSOLUTAMENTE NEUTRAL, OBJETIVA Y DE VERIFICACIÓN FÁCTICA (OSINT). Analiza las noticias de forma fría, pragmática y científica. Tu misión única es establecer los hechos puros y confirmados, separándolos de cualquier retórica o sesgo político. Determina la veracidad y el alcance fáctico de la información."
AI_SYSTEM_PROMPT_MINERVA = "Tu perspectiva es de la OPOSICIÓN VENEZOLANA. Toma los hechos objetivos reportados e interprétalos de forma crítica y analítica. Enfócate en el colapso institucional, la crisis de servicios públicos, las denuncias de censura, violaciones de derechos humanos, protestas ciudadanas y la necesidad de cambio. Mantén un tono intelectual, afilado y frío."
AI_SYSTEM_PROMPT_NEXUS = "Tu perspectiva es del OFICIALISMO VENEZOLANO (Gobierno/Revolución). Toma el análisis de la Oposición y responde en defensa de la soberanía nacional. Enfócate en la resistencia popular ante el bloqueo económico y las sanciones de EE.UU. y sus aliados, los avances estatales y denuncia las críticas opositoras como campaigns de desinformación o intentos de desestabilización."

# ── Configuración Avanzada de Notificaciones y Alertas ──
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_PUSH_CHAT_ID = os.getenv("TELEGRAM_CHANNEL", "")
ALERT_CRITICAL_KEYWORDS = [
    "apagón nacional", "apagón", "corte eléctrico", "blackout", "caída de red",
    "corte de fibra óptica", "falla de borde", "movilización militar", "estado de excepción",
    "toque de queda", "ley marcial", "golpe de estado", "golpe militar", "evacuación diplomática",
    "cierre de fronteras", "restricción de espacio aéreo", "muertos", "fallecidos", "masacre",
    "ejecución", "bomba", "atentado", "explosión", "0-day", "zero-day", "vulnerabilidad crítica",
    "ransomware", "shell upload", "admin access",
    "toma guerrillera", "ataque a oleoducto", "confinamiento", "hostigamiento armado",
    "líder social asesinado", "desplazamiento forzado", "incursión armada", "paro armado",
    "ataque a estación de policía", "bombardeo", "minas antipersona"
]
ALERT_URGENT_KEYWORDS = [
    "decreto presidencial", "providencia administrativa", "expropiación", "intervención",
    "adjudicación directa", "gaceta oficial extraordinaria", "inflación interanual", "déficit fiscal",
    "canasta básica", "reserva internacional", "liquidez monetaria", "devaluación", "desabastecimiento",
    "escasez de combustible", "puerto cerrado", "paralización de transporte", "desvío de carga",
    "sanciones ofac", "embargo comercial", "congelación de activos", "lista negra", "evasión de sanciones",
    "data breach", "exfiltración", "ataque ddos", "leak", "database dump", "credenciales expuestas",
    "protestas", "manifestación", "represión", "gas lacrimógeno", "incendio forestal", "anomalía térmica",
    "fuego masivo", "punto de calor",
    "paz total", "mesa de negociación eln", "cese al fuego", "segunda marquetalia",
    "clan del golfo", "estado mayor central", "calarcá", "antonio garcía",
    "caño limón", "cierre jep", "listado narcoterroristas", "adle"
]

# ── Configuración de Análisis de Sentimiento ──
SENTIMIENTO = {
    "LEXICO_POSITIVO": {
        "recuperación": 3, "crecimiento": 3, "acuerdo": 2, "inversión": 2,
        "estabilidad": 3, "progreso": 3, "avance": 2, "logro": 2, "éxito": 3,
        "aumento": 1, "mejora": 2, "beneficio": 2, "paz": 3, "diálogo": 2,
        "apertura": 2, "libre": 2, "producción": 2, "empleo": 2, "salario": 1,
        "bienestar": 3, "desarrollo": 2, "prosperidad": 3, "solución": 2,
        "esperanza": 2, "victoria": 3, "triunfo": 3, "apoyo": 1, "solidaridad": 2,
        "educación": 1, "salud": 1, "hospital": 0, "vacuna": 1, "medicina": 1,
        "libertad": 2, "democracia": 2, "elecciones": 1, "transparencia": 2,
        "justicia": 2, "derecho": 1, "igualdad": 2, "trabajo": 1,
    },
    "LEXICO_NEGATIVO": {
        "escasez": -3, "sabotaje": -3, "protestas": -2, "huelga": -2, "caos": -3,
        "corrupción": -3, "represión": -3, "violencia": -3, "muertos": -3,
        "crisis": -2, "colapso": -3, "apagón": -2, "racionamiento": -2,
        "inflación": -2, "devaluación": -2, "cierre": -2, "desabastecimiento": -3,
        "detención": -2, "arresto": -2, "represalia": -3, "censura": -2,
        "bloqueo": -2, "embargo": -2, "sanciones": -1, "pobreza": -3,
        "desempleo": -2, "hambre": -3, "miseria": -3, "éxodo": -2, "migración": -1,
        "corte": -2, "falla": -2, "robo": -3, "secuestro": -3,
        "asesinato": -3, "terrorismo": -3, "golpe": -3, "intervención": -2,
        "bulo": -2, "fake": -2, "manipulación": -3, "desinformación": -3,
        "propaganda": -2, "astroturfing": -3,
    },
    "LEXICO_IRA": [
        "indignación", "rechazo", "protesta", "repudio", "denuncia",
        "escándalo", "abuso", "impunidad", "traición", "corruptos",
        "ladrones", "criminales", "dictadura", "tiranía",
    ],
    "LEXICO_MIEDO": [
        "amenaza", "riesgo", "peligro", "alerta", "advertencia", "emergencia",
        "pánico", "crisis", "catástrofe", "desastre", "colapso",
    ],
    "LEXICO_ESPERANZA": [
        "esperanza", "cambio", "futuro", "posibilidad", "oportunidad",
        "solución", "acuerdo", "diálogo", "paz", "libertad", "recuperación",
    ],
    "THRESHOLD_POSITIVO": 0.15,
    "THRESHOLD_NEGATIVO": -0.15,
    "MAX_MUESTRAS": 300,
    "TOP_PALABRAS_LIMIT": 12,
    "BOTS_MUESTRA_LIMIT": 8,
    "CRISIS_MUESTRA_LIMIT": 10,
    "ENTRADAS_MUESTRA_LIMIT": 20,
    "BOT_SCORE_THRESHOLD": 40,
    "CRISIS_SCORE_THRESHOLD": -0.5,
    "CRISIS_KEYWORDS_MIN": 2,
    "ALERTA_SCORE_THRESHOLD": -0.3,
    "ATENCION_SCORE_THRESHOLD": -0.15,
    "BOT_STORM_RATE": 25,
    "SERIE_TEMPORAL_HORAS": 12,
    "NORMALIZACION_DENOM": 0.5,
    "KEYWORDS_CRISIS": [
        "protesta", "huelga", "sabotaje", "escasez", "apagón", "saqueo",
        "disturbio", "represión", "manifestación", "marcha", "paro",
    ],
    "KEYWORDS_BOT": [
        "masivo", "coordinado", "campaña", "fake", "bulo", "viral", "trending",
        "astroturfing", "desinformación", "inorgánico",
    ],
}

ABOUT_US_CONTENT = """
<h2>¿Justicia?</h2>

<strong>¿Dónde está?</strong>

La respuesta no está en un solo lugar ni en una sola persona.
La justicia no desciende del cielo con una capa brillante.

Está en cada mano que verifica una fuente antes de compartirla.
Está en cada mente que cuestiona lo que parece demasiado perfecto.
Está en cada voz que se atreve a decir lo que otros prefieren ignorar.

Está en ti.
Está en nosotros.

Mientras sigamos buscando, contrastando, investigando y exponiendo, la Mentira pierde hilos de su disfraz. Tarde o temprano, el engaño se rompe, las máscaras caen y la Verdad, aunque desnuda, vuelve a ser vista.

No necesitamos ser héroes.
Solo necesitamos negarnos a apartar la mirada.

Aquí no disfrazamos la realidad.
Aquí la enfrentamos, tal como es.

Porque la verdad, aunque desnuda, siempre merece ser vista.
"""

# ── Dominios permitidos ──
ALLOWED_SCHEMES = ("http", "https")

# ── OSIRIS Engine Config ──
OSIRIS_RECON_ENABLED = True
OSIRIS_INTEL_ENABLED = True
OSIRIS_MAP_ENABLED = True
OSIRIS_CCTV_ENABLED = True
OSIRIS_FEED_ENABLED = True
OSIRIS_SANCTIONS_REFRESH_HOURS = 24
OSIRIS_CCTV_INTERVAL_SEC = 300
OSIRIS_MARKETS_INTERVAL_SEC = 600
OSIRIS_CYBER_INTERVAL_SEC = 300
OSIRIS_AEROSPACE_INTERVAL_SEC = 120
OSIRIS_DISASTERS_INTERVAL_SEC = 300
OSIRIS_FEED_INTERVAL_SEC = 120
OSIRIS_MAP_FLIGHTS_INTERVAL_SEC = 60
OSIRIS_MAP_SATELLITES_INTERVAL_SEC = 120
OSIRIS_MAP_EARTHQUAKES_INTERVAL_SEC = 120
OSIRIS_MAP_FIRES_INTERVAL_SEC = 120
OSIRIS_MAP_WEATHER_INTERVAL_SEC = 300
OSIRIS_MAP_CCTV_INTERVAL_SEC = 300

# Objetivos de Rastreo
TRACKING_AIRCRAFT = {
    "0D830B": "FAV0001",
    "0D830C": "FAV0264",
    "0D8249": "YV3016",
    "0D08E7": "YV3507",
    "0D8180": "FANB-C130",
    "43BE51": "Iran-Air",
}

TRACKING_VESSELS = {
    "735059048": "Ayacucho",
    "735059049": "Junin",
}

ALLOWED_DOMAINS = {
    # Redes Sociales / Mensajería
    "t.me",
    # Venezuela / Noticias
    "elnacional.com",
    "elestimulo.com",
    "ipysvenezuela.org",
    "noticierodigital.com",
    "eldiario.com",
    "aporrea.org",
    "telesurtv.net",
    "avn.info.ve",
    "misionverdad.com",
    "laiguana.tv",
    "runrun.es",
    "efectococuyo.com",
    "talcualdigital.com",
    "caracaschronicles.com",
    "ntn24.com",
    "evtv.online",
    "infobae.com",
    "bbc.com",
    "vozdeamerica.com",
    "cnnespanol.cnn.com",
    "elpais.com",
    "venezuelanalysis.com",
    "dolartoday.com",
    "elpitazo.net",
    "cronica.uno",
    "dw.com",
    "ultimasnoticias.com.ve",
    "2001online.com",
    "eluniversal.com",
    "elimpulso.com",
    "el-carabobeno.com",
    "lapatilla.com",
    "alnavio.com",
    "undercodenews.com",
    "descifrado.com",
    "bancaynegocios.com",
    "finanzasdigital.com",
    "monitordolarvenezuela.com",
    "dolarvenezuela.com",
    "vtv.com.ve",
    "suscerte.gob.ve",
    # Internacional
    "reuters.com",
    "theguardian.com",
    "aljazeera.com",
    "apnews.com",
    "feeds.bbci.co.uk",
    "france24.com",
    "rss.cnn.com",
    # Ciberseguridad
    "krebsonsecurity.com",
    "schneier.com",
    "bleepingcomputer.com",
    "malwarebytes.com",
    "troyhunt.com",
    "isc.sans.edu",
    "darkreading.com",
    # IA / Tech
    "huggingface.co",
    "research.google",
    "openai.com",
    "deepmind.com",
    "arxiv.org",
    "realpython.com",
    "blog.python.org",
    "lwn.net",
    "hnrss.org",
    "phoronix.com",
    # OSINT
    "privacyguides.org",
    "eff.org",
    "osintcurio.us",
    "bellingcat.com",
    "recordedfuture.com",
    # Español tech
    "genbeta.com",
    "xataka.com",
    "apuntesdeseguridad.com",
    # Regional
    "stabroeknews.com",
    "kaieteurnewsonline.com",
    "guyanachronicle.com",
    "newsroom.gy",
    "caribbeannewsglobal.com",
    "jamaica-gleaner.com",
    "oglobo.globo.com",
    # Derechos humanos
    "provea.org.ve",
    "hrw.org",
    # Análisis
    "insightcrime.org",
    "venezuelanalysis.com",
    # Colombia / Frontera
    "eltiempo.com",
    "elespectador.com",
    "semana.com",
    "caracol.com.co",
    "rcnradio.com",
    "caracoltv.com",
    "lasillavacia.com",
    "larepublica.co",
    "portafolio.co",
    "laopinion.com.co",
    "elheraldo.co",
    "elcolombiano.com",
    "cuestionpublica.com",
    "wradio.com.co",
    "rtvcnoticias.com",
    "vanguardia.com",
    "elpais.com.co",
    "lafm.com.co",
    "bluradio.com",
    "cambiocolombia.com",
    "verdadabierta.com",
    "pares.com.co",
    # Energía
    "energialatina.com",
}


# ── Funciones de validación opcionales ──
def validate_feeds():
    """Valida que todos los feeds tengan URLs válidas"""
    errores = []
    for nombre, url in RSS_FEEDS.items():
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_SCHEMES:
            errores.append(f"{nombre}: esquema inválido '{parsed.scheme}'")
        if not parsed.netloc:
            errores.append(f"{nombre}: dominio vacío")
        domain = parsed.netloc.lower()
        if not any(domain == d or domain.endswith("." + d) for d in ALLOWED_DOMAINS):
            errores.append(f"{nombre}: dominio no permitido '{domain}'")
    return errores


def get_all_sources():
    """Retorna todas las fuentes incluyendo RSS y Telegram"""
    all_sources = dict(RSS_FEEDS)
    all_sources.update(TELEGRAM_SOURCES)
    return all_sources


# ────────────────────────────────────────────────
# CARGA Y GUARDADO DINÁMICO DE CONFIGURACIÓN
# ────────────────────────────────────────────────
DYNAMIC_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_dynamic.json")

def load_dynamic_config():
    global RSS_FEEDS, TELEGRAM_SOURCES, PRIORITY_FEEDS, CACHE_MAX_AGE_MINUTES, ENTRY_MAX_AGE_HOURS, CYCLE_INTERVAL_MINUTES
    global SSL_VERIFY, RESIDENTIAL_PROXY_URL, USE_TOR_FALLBACK, TOR_SOCKS_PORT, TARGET_USERS, KEYWORDS, PAGE_TITLE, PAGE_DESCRIPTION
    global SITE_URL, TELEGRAM_CHANNEL, LOGO_PATH, LOGO_FALLBACK, ABOUT_US_CONTENT, ALLOWED_DOMAINS
    global DEFCON_LEVEL, DATA_RETENTION_DAYS, SIMILARITY_THRESHOLD, MODULE_OSINT_ACTIVE, MODULE_SOCIAL_ACTIVE, MODULE_NLP_ACTIVE
    global SOCIAL_FETCH_BATCH_SIZE, REGIONAL_BBOX, TRACKING_AIRCRAFT, TRACKING_VESSELS
    global SEISMIC_MONITOR_ENABLED, SEISMIC_TARGET_LAT, SEISMIC_TARGET_LON, SEISMIC_MAX_DISTANCE_KM, SEISMIC_MIN_MAGNITUDE
    global GDACS_MONITOR_ENABLED, GDACS_MAX_DISTANCE_KM, GDACS_EVENT_DAYS
    global ASN_MONITOR_ENABLED, ASN_DROP_THRESHOLD
    global AI_MODEL, AI_TEMPERATURE, AI_MAX_TOKENS, AI_SYSTEM_PROMPT_ARES, AI_SYSTEM_PROMPT_MINERVA, AI_SYSTEM_PROMPT_NEXUS
    global OLLAMA_ENABLED, OLLAMA_HOST, OLLAMA_PORT, OLLAMA_MODEL, OLLAMA_TIMEOUT
    global TELEGRAM_PUSH_CHAT_ID, ALERT_CRITICAL_KEYWORDS, ALERT_URGENT_KEYWORDS
    global SENTIMIENTO
    global OSIRIS_RECON_ENABLED, OSIRIS_INTEL_ENABLED, OSIRIS_MAP_ENABLED, OSIRIS_CCTV_ENABLED, OSIRIS_FEED_ENABLED
    global OSIRIS_SANCTIONS_REFRESH_HOURS
    global OSIRIS_CCTV_INTERVAL_SEC, OSIRIS_MARKETS_INTERVAL_SEC, OSIRIS_CYBER_INTERVAL_SEC
    global OSIRIS_AEROSPACE_INTERVAL_SEC, OSIRIS_DISASTERS_INTERVAL_SEC, OSIRIS_FEED_INTERVAL_SEC
    global OSIRIS_MAP_FLIGHTS_INTERVAL_SEC, OSIRIS_MAP_SATELLITES_INTERVAL_SEC, OSIRIS_MAP_EARTHQUAKES_INTERVAL_SEC
    global OSIRIS_MAP_FIRES_INTERVAL_SEC, OSIRIS_MAP_WEATHER_INTERVAL_SEC, OSIRIS_MAP_CCTV_INTERVAL_SEC

    from database import get_system_settings, save_system_settings

    # Intentar cargar desde la Capa B (PostgreSQL o SQLite)
    data = None
    try:
        data = get_system_settings("dynamic_config")
    except Exception as e:
        _logger.error(f"Fallo al leer config de BD: {e}")

    # Fallback al archivo físico si no hay datos en la DB
    if not data and os.path.exists(DYNAMIC_CONFIG_PATH):
        try:
            with open(DYNAMIC_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Migramos los datos leídos del archivo a la Base de Datos para uso futuro
            save_system_settings(data, "dynamic_config")
        except Exception as e:
            _logger.error(f"Error cargando config_dynamic.json: {e}")
            return

    # Si no existe ni en DB ni en archivo, inicializamos
    if not data:
        data = {
            "RSS_FEEDS": RSS_FEEDS,
            "TELEGRAM_SOURCES": TELEGRAM_SOURCES,
            "PRIORITY_FEEDS": PRIORITY_FEEDS,
            "CACHE_MAX_AGE_MINUTES": CACHE_MAX_AGE_MINUTES,
            "ENTRY_MAX_AGE_HOURS": ENTRY_MAX_AGE_HOURS,
            "CYCLE_INTERVAL_MINUTES": CYCLE_INTERVAL_MINUTES,
            "DEFCON_LEVEL": DEFCON_LEVEL,
            "DATA_RETENTION_DAYS": DATA_RETENTION_DAYS,
            "SIMILARITY_THRESHOLD": SIMILARITY_THRESHOLD,
            "MODULE_OSINT_ACTIVE": MODULE_OSINT_ACTIVE,
            "MODULE_SOCIAL_ACTIVE": MODULE_SOCIAL_ACTIVE,
            "MODULE_NLP_ACTIVE": MODULE_NLP_ACTIVE,
            "SOCIAL_FETCH_BATCH_SIZE": SOCIAL_FETCH_BATCH_SIZE,
            "REGIONAL_BBOX": REGIONAL_BBOX,
            "TRACKING_AIRCRAFT": TRACKING_AIRCRAFT,
            "TRACKING_VESSELS": TRACKING_VESSELS,
            "SSL_VERIFY": SSL_VERIFY,
            "RESIDENTIAL_PROXY_URL": RESIDENTIAL_PROXY_URL,
            "USE_TOR_FALLBACK": USE_TOR_FALLBACK,
            "TOR_SOCKS_PORT": TOR_SOCKS_PORT,
            "TARGET_USERS": TARGET_USERS,
            "KEYWORDS": KEYWORDS,
            "PAGE_TITLE": PAGE_TITLE,
            "PAGE_DESCRIPTION": PAGE_DESCRIPTION,
            "SITE_URL": SITE_URL,
            "TELEGRAM_CHANNEL": TELEGRAM_CHANNEL,
            "LOGO_PATH": LOGO_PATH,
            "LOGO_FALLBACK": LOGO_FALLBACK,
            "ABOUT_US_CONTENT": ABOUT_US_CONTENT,
            "ALLOWED_DOMAINS": list(ALLOWED_DOMAINS),
            "AI_MODEL": AI_MODEL,
            "AI_TEMPERATURE": AI_TEMPERATURE,
            "AI_MAX_TOKENS": AI_MAX_TOKENS,
            "AI_SYSTEM_PROMPT_ARES": AI_SYSTEM_PROMPT_ARES,
            "AI_SYSTEM_PROMPT_MINERVA": AI_SYSTEM_PROMPT_MINERVA,
            "AI_SYSTEM_PROMPT_NEXUS": AI_SYSTEM_PROMPT_NEXUS,
            "OLLAMA_ENABLED": OLLAMA_ENABLED,
            "OLLAMA_HOST": OLLAMA_HOST,
            "OLLAMA_PORT": OLLAMA_PORT,
            "OLLAMA_MODEL": OLLAMA_MODEL,
            "OLLAMA_TIMEOUT": OLLAMA_TIMEOUT,
            "TELEGRAM_PUSH_CHAT_ID": TELEGRAM_PUSH_CHAT_ID,
            "ALERT_CRITICAL_KEYWORDS": ALERT_CRITICAL_KEYWORDS,
            "ALERT_URGENT_KEYWORDS": ALERT_URGENT_KEYWORDS,
            "SENTIMIENTO": SENTIMIENTO,
            "SEISMIC_MONITOR_ENABLED": SEISMIC_MONITOR_ENABLED,
            "SEISMIC_TARGET_LAT": SEISMIC_TARGET_LAT,
            "SEISMIC_TARGET_LON": SEISMIC_TARGET_LON,
            "SEISMIC_MAX_DISTANCE_KM": SEISMIC_MAX_DISTANCE_KM,
            "SEISMIC_MIN_MAGNITUDE": SEISMIC_MIN_MAGNITUDE,
            "GDACS_MONITOR_ENABLED": GDACS_MONITOR_ENABLED,
            "GDACS_MAX_DISTANCE_KM": GDACS_MAX_DISTANCE_KM,
            "GDACS_EVENT_DAYS": GDACS_EVENT_DAYS,
            "ASN_MONITOR_ENABLED": ASN_MONITOR_ENABLED,
            "ASN_DROP_THRESHOLD": ASN_DROP_THRESHOLD,
            "OSIRIS_RECON_ENABLED": OSIRIS_RECON_ENABLED,
            "OSIRIS_INTEL_ENABLED": OSIRIS_INTEL_ENABLED,
            "OSIRIS_MAP_ENABLED": OSIRIS_MAP_ENABLED,
            "OSIRIS_CCTV_ENABLED": OSIRIS_CCTV_ENABLED,
            "OSIRIS_FEED_ENABLED": OSIRIS_FEED_ENABLED,
            "OSIRIS_SANCTIONS_REFRESH_HOURS": OSIRIS_SANCTIONS_REFRESH_HOURS,
            "OSIRIS_CCTV_INTERVAL_SEC": OSIRIS_CCTV_INTERVAL_SEC,
            "OSIRIS_MARKETS_INTERVAL_SEC": OSIRIS_MARKETS_INTERVAL_SEC,
            "OSIRIS_CYBER_INTERVAL_SEC": OSIRIS_CYBER_INTERVAL_SEC,
            "OSIRIS_AEROSPACE_INTERVAL_SEC": OSIRIS_AEROSPACE_INTERVAL_SEC,
            "OSIRIS_DISASTERS_INTERVAL_SEC": OSIRIS_DISASTERS_INTERVAL_SEC,
            "OSIRIS_FEED_INTERVAL_SEC": OSIRIS_FEED_INTERVAL_SEC,
            "OSIRIS_MAP_FLIGHTS_INTERVAL_SEC": OSIRIS_MAP_FLIGHTS_INTERVAL_SEC,
            "OSIRIS_MAP_SATELLITES_INTERVAL_SEC": OSIRIS_MAP_SATELLITES_INTERVAL_SEC,
            "OSIRIS_MAP_EARTHQUAKES_INTERVAL_SEC": OSIRIS_MAP_EARTHQUAKES_INTERVAL_SEC,
            "OSIRIS_MAP_FIRES_INTERVAL_SEC": OSIRIS_MAP_FIRES_INTERVAL_SEC,
            "OSIRIS_MAP_WEATHER_INTERVAL_SEC": OSIRIS_MAP_WEATHER_INTERVAL_SEC,
            "OSIRIS_MAP_CCTV_INTERVAL_SEC": OSIRIS_MAP_CCTV_INTERVAL_SEC
        }
        save_dynamic_config(data)
        return

    try:

        # Mutar colecciones mutables en su lugar
        if "RSS_FEEDS" in data and isinstance(data["RSS_FEEDS"], dict):
            RSS_FEEDS.clear()
            RSS_FEEDS.update(data["RSS_FEEDS"])

        if "TELEGRAM_SOURCES" in data and isinstance(data["TELEGRAM_SOURCES"], dict):
            TELEGRAM_SOURCES.clear()
            TELEGRAM_SOURCES.update(data["TELEGRAM_SOURCES"])

        if "PRIORITY_FEEDS" in data and isinstance(data["PRIORITY_FEEDS"], list):
            PRIORITY_FEEDS.clear()
            PRIORITY_FEEDS.extend(data["PRIORITY_FEEDS"])

        if "TARGET_USERS" in data and isinstance(data["TARGET_USERS"], list):
            TARGET_USERS.clear()
            TARGET_USERS.extend(data["TARGET_USERS"])

        if "KEYWORDS" in data and isinstance(data["KEYWORDS"], list):
            KEYWORDS.clear()
            KEYWORDS.extend(data["KEYWORDS"])

        if "ALLOWED_DOMAINS" in data and isinstance(data["ALLOWED_DOMAINS"], list):
            ALLOWED_DOMAINS.clear()
            ALLOWED_DOMAINS.update(data["ALLOWED_DOMAINS"])

        if "ALERT_CRITICAL_KEYWORDS" in data and isinstance(data["ALERT_CRITICAL_KEYWORDS"], list):
            ALERT_CRITICAL_KEYWORDS.clear()
            ALERT_CRITICAL_KEYWORDS.extend(data["ALERT_CRITICAL_KEYWORDS"])

        if "ALERT_URGENT_KEYWORDS" in data and isinstance(data["ALERT_URGENT_KEYWORDS"], list):
            ALERT_URGENT_KEYWORDS.clear()
            ALERT_URGENT_KEYWORDS.extend(data["ALERT_URGENT_KEYWORDS"])

        # Re-enlazar variables inmutables
        if "CACHE_MAX_AGE_MINUTES" in data:
            CACHE_MAX_AGE_MINUTES = int(data["CACHE_MAX_AGE_MINUTES"])
        if "ENTRY_MAX_AGE_HOURS" in data:
            ENTRY_MAX_AGE_HOURS = int(data["ENTRY_MAX_AGE_HOURS"])
        if "CYCLE_INTERVAL_MINUTES" in data:
            CYCLE_INTERVAL_MINUTES = int(data["CYCLE_INTERVAL_MINUTES"])
        if "DEFCON_LEVEL" in data:
            DEFCON_LEVEL = int(data["DEFCON_LEVEL"])
        if "DATA_RETENTION_DAYS" in data:
            DATA_RETENTION_DAYS = int(data["DATA_RETENTION_DAYS"])
        if "SIMILARITY_THRESHOLD" in data:
            SIMILARITY_THRESHOLD = float(data["SIMILARITY_THRESHOLD"])
        if "MODULE_OSINT_ACTIVE" in data:
            MODULE_OSINT_ACTIVE = bool(data["MODULE_OSINT_ACTIVE"])
        if "MODULE_SOCIAL_ACTIVE" in data:
            MODULE_SOCIAL_ACTIVE = bool(data["MODULE_SOCIAL_ACTIVE"])
        if "MODULE_NLP_ACTIVE" in data:
            MODULE_NLP_ACTIVE = bool(data["MODULE_NLP_ACTIVE"])
        if "SOCIAL_FETCH_BATCH_SIZE" in data:
            SOCIAL_FETCH_BATCH_SIZE = int(data["SOCIAL_FETCH_BATCH_SIZE"])
        if "REGIONAL_BBOX" in data and isinstance(data["REGIONAL_BBOX"], dict):
            REGIONAL_BBOX.clear()
            REGIONAL_BBOX.update(data["REGIONAL_BBOX"])
        if "TRACKING_AIRCRAFT" in data and isinstance(data["TRACKING_AIRCRAFT"], dict):
            TRACKING_AIRCRAFT.clear()
            TRACKING_AIRCRAFT.update(data["TRACKING_AIRCRAFT"])
        if "TRACKING_VESSELS" in data and isinstance(data["TRACKING_VESSELS"], dict):
            TRACKING_VESSELS.clear()
            TRACKING_VESSELS.update(data["TRACKING_VESSELS"])
        if "SSL_VERIFY" in data:
            SSL_VERIFY = bool(data["SSL_VERIFY"])
        if "RESIDENTIAL_PROXY_URL" in data:
            RESIDENTIAL_PROXY_URL = data["RESIDENTIAL_PROXY_URL"]
        if "USE_TOR_FALLBACK" in data:
            USE_TOR_FALLBACK = bool(data["USE_TOR_FALLBACK"])
        if "TOR_SOCKS_PORT" in data:
            TOR_SOCKS_PORT = int(data["TOR_SOCKS_PORT"])
        if "PAGE_TITLE" in data:
            PAGE_TITLE = data["PAGE_TITLE"]
        if "PAGE_DESCRIPTION" in data:
            PAGE_DESCRIPTION = data["PAGE_DESCRIPTION"]
        if "SITE_URL" in data:
            SITE_URL = data["SITE_URL"]
        if "TELEGRAM_CHANNEL" in data:
            TELEGRAM_CHANNEL = data["TELEGRAM_CHANNEL"]
        if "LOGO_PATH" in data:
            LOGO_PATH = data["LOGO_PATH"] if data["LOGO_PATH"] and data["LOGO_PATH"] != "123.png" else "/static/icons/icon-512.png"
        if "LOGO_FALLBACK" in data:
            LOGO_FALLBACK = data["LOGO_FALLBACK"] if data["LOGO_FALLBACK"] else "/static/icons/icon-192.png"
        if "ABOUT_US_CONTENT" in data:
            ABOUT_US_CONTENT = data["ABOUT_US_CONTENT"]
        if "AI_MODEL" in data:
            AI_MODEL = str(data["AI_MODEL"])
        if "AI_TEMPERATURE" in data:
            AI_TEMPERATURE = float(data["AI_TEMPERATURE"])
        if "AI_MAX_TOKENS" in data:
            AI_MAX_TOKENS = int(data["AI_MAX_TOKENS"])
        if "AI_SYSTEM_PROMPT_ARES" in data:
            AI_SYSTEM_PROMPT_ARES = str(data["AI_SYSTEM_PROMPT_ARES"])
        if "AI_SYSTEM_PROMPT_MINERVA" in data:
            AI_SYSTEM_PROMPT_MINERVA = str(data["AI_SYSTEM_PROMPT_MINERVA"])
        if "AI_SYSTEM_PROMPT_NEXUS" in data:
            AI_SYSTEM_PROMPT_NEXUS = str(data["AI_SYSTEM_PROMPT_NEXUS"])

        if "OLLAMA_ENABLED" in data:
            OLLAMA_ENABLED = bool(data["OLLAMA_ENABLED"])
        if "OLLAMA_HOST" in data:
            OLLAMA_HOST = str(data["OLLAMA_HOST"])
        if "OLLAMA_PORT" in data:
            OLLAMA_PORT = int(data["OLLAMA_PORT"])
        if "OLLAMA_MODEL" in data:
            OLLAMA_MODEL = str(data["OLLAMA_MODEL"])
        if "OLLAMA_TIMEOUT" in data:
            OLLAMA_TIMEOUT = float(data["OLLAMA_TIMEOUT"])
        if "TELEGRAM_PUSH_CHAT_ID" in data:
            TELEGRAM_PUSH_CHAT_ID = str(data["TELEGRAM_PUSH_CHAT_ID"])

        if "SEISMIC_MONITOR_ENABLED" in data:
            SEISMIC_MONITOR_ENABLED = bool(data["SEISMIC_MONITOR_ENABLED"])
        if "SEISMIC_TARGET_LAT" in data:
            SEISMIC_TARGET_LAT = float(data["SEISMIC_TARGET_LAT"])
        if "SEISMIC_TARGET_LON" in data:
            SEISMIC_TARGET_LON = float(data["SEISMIC_TARGET_LON"])
        if "SEISMIC_MAX_DISTANCE_KM" in data:
            SEISMIC_MAX_DISTANCE_KM = float(data["SEISMIC_MAX_DISTANCE_KM"])
        if "SEISMIC_MIN_MAGNITUDE" in data:
            SEISMIC_MIN_MAGNITUDE = float(data["SEISMIC_MIN_MAGNITUDE"])

        if "GDACS_MONITOR_ENABLED" in data:
            GDACS_MONITOR_ENABLED = bool(data["GDACS_MONITOR_ENABLED"])
        if "GDACS_MAX_DISTANCE_KM" in data:
            GDACS_MAX_DISTANCE_KM = float(data["GDACS_MAX_DISTANCE_KM"])
        if "GDACS_EVENT_DAYS" in data:
            GDACS_EVENT_DAYS = int(data["GDACS_EVENT_DAYS"])

        if "ASN_MONITOR_ENABLED" in data:
            ASN_MONITOR_ENABLED = bool(data["ASN_MONITOR_ENABLED"])
        if "ASN_DROP_THRESHOLD" in data:
            ASN_DROP_THRESHOLD = float(data["ASN_DROP_THRESHOLD"])

        # ── OSIRIS Engine dynamic config ──
        if "OSIRIS_RECON_ENABLED" in data:
            OSIRIS_RECON_ENABLED = bool(data["OSIRIS_RECON_ENABLED"])
        if "OSIRIS_INTEL_ENABLED" in data:
            OSIRIS_INTEL_ENABLED = bool(data["OSIRIS_INTEL_ENABLED"])
        if "OSIRIS_MAP_ENABLED" in data:
            OSIRIS_MAP_ENABLED = bool(data["OSIRIS_MAP_ENABLED"])
        if "OSIRIS_CCTV_ENABLED" in data:
            OSIRIS_CCTV_ENABLED = bool(data["OSIRIS_CCTV_ENABLED"])
        if "OSIRIS_FEED_ENABLED" in data:
            OSIRIS_FEED_ENABLED = bool(data["OSIRIS_FEED_ENABLED"])
        if "OSIRIS_SANCTIONS_REFRESH_HOURS" in data:
            OSIRIS_SANCTIONS_REFRESH_HOURS = int(data["OSIRIS_SANCTIONS_REFRESH_HOURS"])
        if "OSIRIS_CCTV_INTERVAL_SEC" in data:
            OSIRIS_CCTV_INTERVAL_SEC = int(data["OSIRIS_CCTV_INTERVAL_SEC"])
        if "OSIRIS_MARKETS_INTERVAL_SEC" in data:
            OSIRIS_MARKETS_INTERVAL_SEC = int(data["OSIRIS_MARKETS_INTERVAL_SEC"])
        if "OSIRIS_CYBER_INTERVAL_SEC" in data:
            OSIRIS_CYBER_INTERVAL_SEC = int(data["OSIRIS_CYBER_INTERVAL_SEC"])
        if "OSIRIS_AEROSPACE_INTERVAL_SEC" in data:
            OSIRIS_AEROSPACE_INTERVAL_SEC = int(data["OSIRIS_AEROSPACE_INTERVAL_SEC"])
        if "OSIRIS_DISASTERS_INTERVAL_SEC" in data:
            OSIRIS_DISASTERS_INTERVAL_SEC = int(data["OSIRIS_DISASTERS_INTERVAL_SEC"])
        if "OSIRIS_FEED_INTERVAL_SEC" in data:
            OSIRIS_FEED_INTERVAL_SEC = int(data["OSIRIS_FEED_INTERVAL_SEC"])
        if "OSIRIS_MAP_FLIGHTS_INTERVAL_SEC" in data:
            OSIRIS_MAP_FLIGHTS_INTERVAL_SEC = int(data["OSIRIS_MAP_FLIGHTS_INTERVAL_SEC"])
        if "OSIRIS_MAP_SATELLITES_INTERVAL_SEC" in data:
            OSIRIS_MAP_SATELLITES_INTERVAL_SEC = int(data["OSIRIS_MAP_SATELLITES_INTERVAL_SEC"])
        if "OSIRIS_MAP_EARTHQUAKES_INTERVAL_SEC" in data:
            OSIRIS_MAP_EARTHQUAKES_INTERVAL_SEC = int(data["OSIRIS_MAP_EARTHQUAKES_INTERVAL_SEC"])
        if "OSIRIS_MAP_FIRES_INTERVAL_SEC" in data:
            OSIRIS_MAP_FIRES_INTERVAL_SEC = int(data["OSIRIS_MAP_FIRES_INTERVAL_SEC"])
        if "OSIRIS_MAP_WEATHER_INTERVAL_SEC" in data:
            OSIRIS_MAP_WEATHER_INTERVAL_SEC = int(data["OSIRIS_MAP_WEATHER_INTERVAL_SEC"])
        if "OSIRIS_MAP_CCTV_INTERVAL_SEC" in data:
            OSIRIS_MAP_CCTV_INTERVAL_SEC = int(data["OSIRIS_MAP_CCTV_INTERVAL_SEC"])

        if "SENTIMIENTO" in data and isinstance(data["SENTIMIENTO"], dict):
            cfg_s = data["SENTIMIENTO"]
            for key in ("LEXICO_POSITIVO", "LEXICO_NEGATIVO", "LEXICO_IRA", "LEXICO_MIEDO",
                        "LEXICO_ESPERANZA", "KEYWORDS_CRISIS", "KEYWORDS_BOT"):
                if key in cfg_s:
                    SENTIMIENTO[key] = cfg_s[key]
            for key in ("THRESHOLD_POSITIVO", "THRESHOLD_NEGATIVO", "MAX_MUESTRAS",
                        "TOP_PALABRAS_LIMIT", "BOTS_MUESTRA_LIMIT", "CRISIS_MUESTRA_LIMIT",
                        "ENTRADAS_MUESTRA_LIMIT", "BOT_SCORE_THRESHOLD", "CRISIS_SCORE_THRESHOLD",
                        "CRISIS_KEYWORDS_MIN", "ALERTA_SCORE_THRESHOLD", "ATENCION_SCORE_THRESHOLD",
                        "BOT_STORM_RATE", "SERIE_TEMPORAL_HORAS", "NORMALIZACION_DENOM"):
                if key in cfg_s:
                    SENTIMIENTO[key] = cfg_s[key]

    except Exception as e:
        _logger.error(f"Error cargando config_dynamic.json: {e}")

def save_dynamic_config(data):
    try:
        # Asegurar que dominios permitidos se infieran de los feeds RSS agregados
        if "RSS_FEEDS" in data and isinstance(data["RSS_FEEDS"], dict):
            inferred_domains = set(data.get("ALLOWED_DOMAINS", []))
            for url in data["RSS_FEEDS"].values():
                try:
                    parsed = urlparse(url)
                    if parsed.netloc:
                        domain = parsed.netloc.lower()
                        # Quitar www. si existe para normalizar
                        if domain.startswith("www."):
                            domain = domain[4:]
                        inferred_domains.add(domain)
                except Exception:
                     pass
            data["ALLOWED_DOMAINS"] = list(inferred_domains)

        # Guardar en Base de Datos (Capa B)
        from database import save_system_settings
        save_system_settings(data, "dynamic_config")

        # Guardar como backup en archivo físico (escritura atómica)
        tmp_path = DYNAMIC_CONFIG_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, DYNAMIC_CONFIG_PATH)

        load_dynamic_config()

        # Notificar al worker vía Redis PubSub si está disponible
        try:
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                import redis as _redis_mod
                _r = _redis_mod.from_url(redis_url, decode_responses=True)
                _r.publish("cobalto_config", "reloaded")
                _r.connection_pool.disconnect()
        except Exception:
            pass

        return True
    except Exception as e:
        _logger.error(f"Error guardando config en BD/Archivo: {e}")
        return False

# Cargar configuración dinámica al inicio
load_dynamic_config()

# Fin de config.py v7.0.11 – sintaxis limpia, feeds validados, listo para producción
