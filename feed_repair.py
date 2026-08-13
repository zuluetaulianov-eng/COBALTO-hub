# feed_repair.py - Sistema de Auto-reparación de Feeds
# Busca alternativas automáticas para fuentes caídas y guarda "parches" persistentes.

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse

from osint_deep_scraper import scraper

PATCH_FILE = Path(__file__).parent / "feed_patches.json"
logger = logging.getLogger("FeedRepair")


def load_patches() -> Dict[str, str]:
    """Carga los parches de feeds desde el archivo JSON."""
    if PATCH_FILE.exists():
        try:
            with open(PATCH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error cargando parches: {e}")
    return {}


def save_patch(source_name: str, new_url: str):
    """Guarda una nueva URL para una fuente específica."""
    patches = load_patches()
    patches[source_name] = new_url
    try:
        with open(PATCH_FILE, "w", encoding="utf-8") as f:
            json.dump(patches, f, indent=4)
        logger.info(f"[REPAIR] Parche guardado para {source_name}: {new_url}")
    except Exception as e:
        logger.error(f"Error guardando parche: {e}")


async def repair_feed(source_name: str, original_url: str) -> Optional[str]:
    """
    Intenta encontrar una URL alternativa usando DeepScraper.
    Busca en el dominio base por otros endpoints de RSS o APIs.
    """
    logger.info(f"[REPAIR] Iniciando auto-reparación para {source_name}...")

    # Extraer el dominio base
    try:
        parsed = urlparse(original_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"

        # 1. Escanear APIs ocultas en la URL original y en el home
        targets = [original_url, base_domain]
        for target in targets:
            apis = await scraper.extract_hidden_apis(target)

            # Buscar algo que parezca un feed o API de noticias
            potential_urls = apis.get("api_endpoints", []) + apis.get("js_endpoints", [])
            for p_url in potential_urls:
                # Si es relativa, unirla
                full_url = urljoin(base_domain, p_url)

                # Verificar si la nueva URL parece ser un feed válido (simple check)
                if any(x in full_url.lower() for x in ["rss", "feed", "xml", "json", "v1", "v2"]):
                    # Evitar la misma URL que ya sabemos que falla
                    if full_url.strip("/") == original_url.strip("/"):
                        continue

                    logger.info(f"[REPAIR] ¡Posible alternativa encontrada para {source_name}!: {full_url}")
                    # Guardar el parche
                    save_patch(source_name, full_url)
                    return full_url
    except Exception as e:
        logger.error(f"[REPAIR] Error durante reparación de {source_name}: {e}")

    logger.warning(f"[REPAIR] No se encontró alternativa automatizada para {source_name}")
    return None
