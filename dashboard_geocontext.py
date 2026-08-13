import asyncio
import re

GEO_SEMAPHORE = asyncio.Semaphore(2)

CATEGORY_MAP = {
    "📱 Redes Sociales": ["extendidas", "especiales", "reddit", "telegram", "mastodon", "nitter", "tiktok", "instagram", "bluesky"],
    "📰 Noticias": ["news", "agregadores", "latinoam", "intl", "hub", "prensa"],
    "💻 Tecnología": ["github", "stackoverflow", "tech", "osint", "cyber", "hacker", "security"],
    "📊 Datos": ["datos", "crypto", "clima", "econom", "covid", "banca", "finanzas", "dolar"],
    "🕵️ OSINT Deep": ["onion", "dorks", "darkweb", "pastebin"],
    "🛰️ Realtime": ["satélite", "scanner", "radar", "realtime", "vuelos", "marítimo"],
}

def categorize_source(source_name: str) -> str:
    src_lower = source_name.lower()
    for cat, keywords in CATEGORY_MAP.items():
        if any(kw in src_lower for kw in keywords):
            return cat
    return "🌎 Internacional"

# ── MOTOR DE GEOLOCALIZACIÓN PASIVA MASIVA ──

# Diccionario de coordenadas para Venezuela (Estados y Ciudades principales)
VENEZUELA_GEO_DICT = {
    "distrito capital": {"lat": 10.4806, "lon": -66.9036, "tipo": "estado"},
    "caracas": {"lat": 10.4806, "lon": -66.9036, "tipo": "ciudad"},
    "miranda": {"lat": 10.2505, "lon": -66.3302, "tipo": "estado"},
    "zulia": {"lat": 9.8660, "lon": -72.2562, "tipo": "estado"},
    "maracaibo": {"lat": 10.6427, "lon": -71.6125, "tipo": "ciudad"},
    "carabobo": {"lat": 10.1989, "lon": -67.9710, "tipo": "estado"},
    "valencia": {"lat": 10.1620, "lon": -68.0077, "tipo": "ciudad"},
    "lara": {"lat": 10.1061, "lon": -69.6587, "tipo": "estado"},
    "barquisimeto": {"lat": 10.0678, "lon": -69.3474, "tipo": "ciudad"},
    "aragua": {"lat": 10.2353, "lon": -67.2403, "tipo": "estado"},
    "maracay": {"lat": 10.2469, "lon": -67.5958, "tipo": "ciudad"},
    "anzoategui": {"lat": 9.0833, "lon": -64.2500, "tipo": "estado"},
    "barcelona": {"lat": 10.1333, "lon": -64.6833, "tipo": "ciudad"},
    "puerto la cruz": {"lat": 10.2220, "lon": -64.6276, "tipo": "ciudad"},
    "bolivar": {"lat": 6.3333, "lon": -63.5000, "tipo": "estado"},
    "ciudad guayana": {"lat": 8.3617, "lon": -62.6533, "tipo": "ciudad"},
    "tachira": {"lat": 7.8286, "lon": -72.1433, "tipo": "estado"},
    "san cristobal": {"lat": 7.7669, "lon": -72.2250, "tipo": "ciudad"},
    "merida": {"lat": 8.5983, "lon": -71.1449, "tipo": "estado"},
    "sucre": {"lat": 10.4497, "lon": -63.1772, "tipo": "estado"},
    "cumana": {"lat": 10.4633, "lon": -64.1775, "tipo": "ciudad"},
    "falcon": {"lat": 11.2333, "lon": -69.8667, "tipo": "estado"},
    "coro": {"lat": 11.4045, "lon": -69.6734, "tipo": "ciudad"},
    "punto fijo": {"lat": 11.6963, "lon": -70.1805, "tipo": "ciudad"},
    "nueva esparta": {"lat": 10.9920, "lon": -63.9113, "tipo": "estado"},
    "margarita": {"lat": 10.9920, "lon": -63.9113, "tipo": "isla"},
    "monagas": {"lat": 9.3800, "lon": -63.0769, "tipo": "estado"},
    "maturin": {"lat": 9.7457, "lon": -63.1832, "tipo": "ciudad"},
    "barinas": {"lat": 8.1632, "lon": -70.0316, "tipo": "estado"},
    "apure": {"lat": 7.3500, "lon": -68.9333, "tipo": "estado"},
    "yaracuy": {"lat": 10.3333, "lon": -68.7500, "tipo": "estado"},
    "san felipe": {"lat": 10.3399, "lon": -68.7425, "tipo": "ciudad"},
    "guarico": {"lat": 8.8167, "lon": -66.1667, "tipo": "estado"},
    "san juan de los morros": {"lat": 9.9115, "lon": -67.3538, "tipo": "ciudad"},
    "portuguesa": {"lat": 9.1667, "lon": -69.2500, "tipo": "estado"},
    "acarigua": {"lat": 9.5532, "lon": -69.2024, "tipo": "ciudad"},
    "cojedes": {"lat": 9.3333, "lon": -68.3333, "tipo": "estado"},
    "san carlos": {"lat": 9.6612, "lon": -68.5827, "tipo": "ciudad"},
    "delta amacuro": {"lat": 8.5000, "lon": -61.5000, "tipo": "estado"},
    "tucupita": {"lat": 9.0622, "lon": -62.0510, "tipo": "ciudad"},
    "amazonas": {"lat": 3.3333, "lon": -66.1667, "tipo": "estado"},
    "puerto ayacucho": {"lat": 5.6622, "lon": -67.6236, "tipo": "ciudad"},
    "vargas": {"lat": 10.6000, "lon": -66.9333, "tipo": "estado"},
    "la guaira": {"lat": 10.5996, "lon": -66.9314, "tipo": "ciudad"},
    "miraflores": {"lat": 10.5083, "lon": -66.9186, "tipo": "poi"},
    "fuerte tiuna": {"lat": 10.4550, "lon": -66.9350, "tipo": "poi"}
}

# Pre-compilar regex para velocidad extrema O(1)
_GEO_PATTERN = re.compile(r'\b(' + '|'.join(re.escape(k) for k in VENEZUELA_GEO_DICT.keys()) + r')\b', re.IGNORECASE)

def fast_geolocate_venezuela(text: str) -> list[dict]:
    """
    Escanea un texto en milisegundos buscando entidades geográficas de Venezuela.
    Devuelve una lista de ubicaciones encontradas sin tocar el LLM.
    """
    if not text:
        return []

    # Remover acentos básicos para el match
    text_norm = text.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    matches = _GEO_PATTERN.findall(text_norm)

    found = {}
    for match in matches:
        key = match.lower()
        if key in VENEZUELA_GEO_DICT and key not in found:
            # Priorizamos si ya lo encontramos, pero guardamos la primera instancia
            geo_data = VENEZUELA_GEO_DICT[key]
            found[key] = {
                "nombre": match.title(),
                "lat": geo_data["lat"],
                "lon": geo_data["lon"],
                "tipo": geo_data["tipo"]
            }

    return list(found.values())


# ── AGENTE ATLAS (GEOINT HÍBRIDO) ──
import logging

import aiohttp

try:
    from ai_core import get_next_groq_client, report_groq_failure, report_groq_success
except ImportError:
    pass

logger = logging.getLogger(__name__)

async def ai_geolocate_crisis(text: str, source: str = "") -> list[dict]:
    """
    Agente ATLAS (GEOINT).
    Se activa SOLO para reportes críticos.
    Usa Llama-3-8B (ligero y ultra-rápido) para extraer la instalación o localidad exacta.
    Luego cruza con Nominatim/OSM.
    """
    if not text:
        return []

    client = None
    try:
        client = get_next_groq_client()
        if not client:
            return []

        prompt = f"""
Eres el Agente ATLAS, especialista en Inteligencia Geoespacial (GEOINT).
Extrae la ubicación más exacta (nombre de ciudad, refinería, subestación, base militar, puente o barrio) mencionada en este reporte de inteligencia de Venezuela.
Si no hay una ubicación clara, responde exactamente con la palabra "NULA".
Solo responde con el nombre de la ubicación, sin explicaciones.

Reporte: {text}
"""

        # Usamos el modelo más rápido y barato para esto (8B)
        response = await client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=20
        )

        extracted_location = response.choices[0].message.content.strip()
        report_groq_success(client)

        if not extracted_location or extracted_location.upper() == "NULA" or len(extracted_location) < 3:
            return []

        # Paso 2: Geocodificación real con OSM/Nominatim
        query = f"{extracted_location}, Venezuela"
        async with aiohttp.ClientSession() as session:
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}&limit=1"
            async with session.get(url, headers={"User-Agent": "CobaltoHub_ATLAS_Node/1.0"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        return [{
                            "nombre": extracted_location,
                            "lat": float(data[0]["lat"]),
                            "lon": float(data[0]["lon"]),
                            "tipo": "ai_geoint"
                        }]

    except Exception as e:
        logger.error(f"[ATLAS-GEOINT] Error en IA Geocoder: {e}")
        if client:
            report_groq_failure(client)

    return []
