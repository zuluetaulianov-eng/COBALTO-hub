# event_radar.py - Radar de Eventos Críticos en Tiempo Real
# Monitorea palabras clave de alta frecuencia para detectar incidentes antes que los medios oficiales.

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from ai_core import geolocate_text
from social_hub import fetch_bluesky, fetch_rss

logger = logging.getLogger("EventRadar")

# Palabras clave de "Flash Event" para el radar
RADAR_KEYWORDS = [
    "sin luz",
    "apagón",
    "explosión",
    "protesta",
    "trancado",
    "tiroteo",
    "enfrentamiento",
    "detenido",
    "allanamiento",
    "incendio",
    "falla eléctrica",
    "saqueo",
]

# Umbral de viralidad para alertas críticas
VIRAL_THRESHOLD = 1000


class EventRadar:
    """Sistema de monitoreo táctico para detección de eventos."""

    _MAX_SEEN = 5000

    def __init__(self):
        self.active_events = []
        self._seen_ids = set()

    async def scan_flash_events(self) -> List[Dict[str, Any]]:
        """Escanea múltiples fuentes en busca de eventos críticos inmediatos."""
        if len(self._seen_ids) > self._MAX_SEEN:
            self._seen_ids = set(list(self._seen_ids)[-self._MAX_SEEN // 2 :])
        logger.info("[RADAR] Iniciando escaneo de eventos flash...")

        # 1. Monitoreo de Bluesky (AT Protocol) para keywords críticas
        tasks = []
        for kw in RADAR_KEYWORDS[:5]:  # Top 5 prioritarias
            tasks.append(asyncio.to_thread(fetch_bluesky, kw))

        # 2. Monitoreo de feeds de emergencia (si existen)
        tasks.append(asyncio.to_thread(fetch_rss, "Sucesos", "https://t.me/s/notivenezuelaarma"))

        results = await asyncio.gather(*tasks)

        new_events = []
        for batch in results:
            for item in batch:
                if item.get("link") and item["link"] not in self._seen_ids:
                    # Análisis de importancia: ¿Contiene keywords de radar?
                    text = f"{item['title']} {item['summary']}".lower()
                    if any(kw in text for kw in RADAR_KEYWORDS):
                        # Intentar geolocalizar el evento para el mapa
                        geo = await geolocate_text(text)

                        # Extraer métricas de viralidad (vistas) si están en los metadatos
                        views = item.get("metrics", {}).get("views", 0)
                        is_viral = views >= VIRAL_THRESHOLD

                        severity = "INFO"
                        if any(x in text for x in ["explosión", "tiroteo", "muerte"]) or is_viral:
                            severity = "CRITICAL"

                        event = {
                            "type": "RADAR_EVENT",
                            "severity": severity,
                            "viral_alert": is_viral,
                            "views": views,
                            "title": item["title"],
                            "location": geo,
                            "timestamp": datetime.now().isoformat(),
                            "source": item["source"],
                            "link": item["link"],
                        }
                        new_events.append(event)
                        self._seen_ids.add(item["link"])

        logger.info(f"[RADAR] Detectados {len(new_events)} eventos nuevos.")
        return new_events


# Instancia global
radar = EventRadar()

if __name__ == "__main__":

    async def test():
        events = await radar.scan_flash_events()
        for e in events:
            print(f"[{e['severity']}] {e['title']} @ {e['location']}")

    asyncio.run(test())
