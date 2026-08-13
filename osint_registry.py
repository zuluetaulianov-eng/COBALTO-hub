# osint_registry.py - Orquestador Central de Módulos OSINT v1.0
# Registro único, descubrimiento dinámico y carga unificada
import importlib
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Catálogo maestro de módulos ──────────────────────────────────
# Cada entrada: (nombre_módulo, función_principal, etiqueta, tipo_retorno)
# tipo_retorno: "sources" (dict con sources/count), "direct" (valor directo), "special" (import manual)
MODULE_REGISTRY = [
    # ── Hub Consolidado (Recomendado) ──
    ("social_hub", "get_social_hub_data", "Cobalto Hub Unificado", "sources"),
    # ── Social Básicas (Legacy) ──
    ("social_public_extractor", "get_public_social_data", "Básicas (Legacy)", "sources"),
    ("social_extractor_v2", "get_social_data_v2", "Red Team v3 (Legacy)", "sources"),
    ("social_extractor", "get_social_data", "Autenticadas (Legacy)", "sources"),
    ("search_social", "search_social_multiplatform", "Búsqueda Multiplataforma", "sources"),
    # ── Social Extendidas (Legacy) ──
    ("social_extended", "get_extended_sources", "Extendidas (Legacy)", "sources"),
    ("social_extras", "get_special_sources", "Especiales (Legacy)", "sources"),
    ("social_data", "get_data_sources", "Datos (Legacy)", "sources"),
    ("social_more", "get_more_sources", "Más (Legacy)", "sources"),
    # ── OSINT Core ──
    ("osint_onion", "get_onion_data", "Onion", "sources_dict"),
    ("osint_serp", "get_serp_data", "SERP", "sources_dict"),
    ("osint_realtime", "get_realtime_data", "Realtime", "sources_dict"),
    ("osint_pastebin", "get_pastebin_data", "Pastebin", "sources_dict"),
    ("osint_satellite", "get_satellite_data", "Satélite", "sources_dict"),
    ("osint_scanner", "get_emergency_scanner_data", "Scanner", "sources_dict"),
    ("osint_social_dorks", "get_social_dorks_sync", "Dorks Social", "sources_dict"),
    ("osint_github", "get_github_intel", "GitHub Intel", "sources_dict"),
    # ── Extractores de Redes ──
    ("tiktok_extractor", "get_tiktok_all", "TikTok Hashtags", "sources_list"),
    ("tiktok_extractor", "get_tiktok_profiles", "TikTok Perfiles", "sources_list"),
    ("instagram_extractor", "get_instagram_all", "Instagram Hashtags", "sources_list"),
    ("instagram_extractor", "get_instagram_profiles", "Instagram Perfiles", "sources_list"),
    # ── Trackers ──
    ("open_data_apis", "get_all_open_data", "Open Data", "sources_dict"),
    ("flight_tracker", "get_all_flight_data", "Vuelos", "sources_dict"),
    ("vessel_tracker", "get_all_vessel_data", "Embarcaciones", "sources_dict"),
    ("events_tracker", "get_all_events_data", "Eventos", "sources_dict"),
    ("osint_network_resilience", "get_network_resilience_data", "Resiliencia de Red", "sources_dict"),
    ("osint_sigint_alerts", "get_sigint_alerts_data", "Anomalías SIGINT", "sources_dict"),
    ("osint_botnet_detector", "get_botnet_detector_data", "Detector de Botnets", "sources_dict"),
    ("osint_finint", "get_finint_data", "Radar FININT", "sources_dict"),
]

# Módulos especiales que requieren manejo específico (multi-función, parametrizados)
SPECIAL_MODULES = {
    "osint_fakenews": {"functions": ["analyze_batch_news", "get_reliability_summary"]},
    "osint_socialgraph": {
        "functions": [
            "get_social_graph",
            "get_realtime_metrics",
            "get_geographic_locations",
            "calculate_activity_heatmap",
            "detect_bridge_nodes",
        ]
    },
    "osint_alerts": {"functions": ["generate_alerts", "get_alert_summary"]},
    "osint_narrative": {"functions": ["get_narrative_data"]},
    "user_search": {"functions": ["get_user_search_results_for_dashboard", "search_multiple_users_for_dashboard"]},
}

# ── Fallbacks estándar según tipo de retorno ─────────────────────
FALLBACKS = {
    "sources": lambda: {"sources": {}, "count": 0, "timestamp": ""},
    "sources_dict": lambda: {"sources": {}, "count": 0, "timestamp": ""},
    "sources_list": lambda: [],
    "direct": lambda: {},
}


def _import_module(mod_name: str):
    """Importa un módulo con manejo seguro."""
    try:
        return importlib.import_module(mod_name)
    except ImportError as e:
        logger.debug(f"Módulo {mod_name} no disponible: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error al cargar {mod_name}: {e}")
        return None


def load_function(mod_name: str, func_name: str) -> Optional[Callable]:
    """Carga una función específica de un módulo."""
    mod = _import_module(mod_name)
    if mod is None:
        return None
    func = getattr(mod, func_name, None)
    if func is None:
        logger.warning(f"Función {func_name} no encontrada en {mod_name}")
    return func


def load_special_module(mod_name: str) -> Dict[str, Any]:
    """Carga un módulo especial y devuelve todas sus funciones."""
    mod = _import_module(mod_name)
    if mod is None:
        return {}
    spec = SPECIAL_MODULES.get(mod_name, {})
    result = {}
    for func_name in spec.get("functions", []):
        func = getattr(mod, func_name, None)
        if func:
            result[func_name] = func
    return result


def get_all_social_functions() -> List[Tuple[Callable, str]]:
    """Carga todas las funciones de fuentes sociales y devuelve lista (func, label)."""
    tasks = []
    for mod_name, func_name, label, ret_type in MODULE_REGISTRY:
        if ret_type in ("sources", "sources_dict", "sources_list"):
            func = load_function(mod_name, func_name)
            if func:
                tasks.append((func, label))
            else:
                tasks.append((FALLBACKS[ret_type], label))
    return tasks


def call_function_safe(func: Callable, label: str, *args, **kwargs) -> Any:
    """Ejecuta una función con captura segura de errores."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"[OSINT REGISTRY] Error en {label}: {e}")
        return FALLBACKS.get("sources", lambda: {})()


def get_available_modules() -> List[str]:
    """Devuelve lista de módulos OSINT realmente disponibles en disco."""
    project_dir = Path(__file__).parent
    modules = set()
    for mod_name, _, _, _ in MODULE_REGISTRY:
        mod_path = project_dir / f"{mod_name}.py"
        if mod_path.exists():
            modules.add(mod_name)
    for mod_name in SPECIAL_MODULES:
        mod_path = project_dir / f"{mod_name}.py"
        if mod_path.exists():
            modules.add(mod_name)
    return sorted(modules)


def get_module_stats() -> Dict[str, Any]:
    """Estadísticas del registry para diagnóstico."""
    available = get_available_modules()
    total = len(MODULE_REGISTRY) + len(SPECIAL_MODULES)
    return {
        "total_registered": total,
        "available_on_disk": len(available),
        "modules": available,
        "loaded_functions": len(get_all_social_functions()),
    }
