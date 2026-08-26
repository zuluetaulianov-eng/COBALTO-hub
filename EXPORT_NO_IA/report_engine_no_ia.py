"""
REPORT ENGINE NO-IA (Motor Determinista de Generación de Informes de Inteligencia)
==================================================================================
Sistema autónomo de generación de informes de inteligencia basado en reglas,
heurísticas deterministas, matrices de riesgo y análisis de datos estadísticos.
NO REQUIERE NINGUNA API DE IA O LLM EXTERNO.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("ReportEngineNoIA")

# ── Palabras Clave y Ponderación de Amenaza (Heurística Determinista) ──
CRISIS_KEYWORDS = {
    "critica": ["ataque", "bomba", "explosion", "muertos", "emboscada", "sabotaje", "ciberataque", "ransomware", "golpe", "desastre"],
    "alta": ["protesta", "enfrentamiento", "detencion", "apagon", "falla", "amaneza", "frontera", "huelga", "fuerza armada", "militar"],
    "media": ["declaracion", "sancion", "gobierno", "ley", "decreto", "eleccion", "inflacion", "dolar", "comercio", "cierre"],
}

SOURCE_RELIABILITY = {
    "oficial": 0.9,
    "prensa_nacional": 0.8,
    "prensa_regional": 0.7,
    "redes_sociales": 0.5,
    "desconocida": 0.4,
}


def calcular_score_amenaza(titulo: str, contenido: str) -> Tuple[str, float]:
    """Calcula deterministamente el nivel de amenaza y un score de 0.0 a 1.0 basado en palabras clave."""
    texto = f"{titulo} {contenido}".lower()
    score = 0.0

    for kw in CRISIS_KEYWORDS["critica"]:
        if kw in texto:
            score += 0.35
    for kw in CRISIS_KEYWORDS["alta"]:
        if kw in texto:
            score += 0.20
    for kw in CRISIS_KEYWORDS["media"]:
        if kw in texto:
            score += 0.08

    score = min(score, 1.0)

    if score >= 0.70:
        nivel = "CRÍTICA"
    elif score >= 0.40:
        nivel = "ALTA"
    elif score >= 0.20:
        nivel = "MEDIA"
    else:
        nivel = "BAJA"

    return nivel, round(score, 2)


def extraer_actores_clave(texto: str) -> List[str]:
    """Extrae nombres de instituciones, entidades u organizaciones usando reglas sintácticas y expresiones regulares."""
    patron_entidades = r"\b(?:FANB|PNB|SEBIN|DGCIM|BCV|PDVSA|Asamblea Nacional|Gobierno|Oposición|Ministerio|Fuerzas Armadas|Cancillería|OEA|ONU)\b"
    coincidencias = list(set(re.findall(patron_entidades, texto, re.IGNORECASE)))
    return coincidencias if coincidencias else ["Actores No Especificados"]


def generar_resumen_determinista(titulo: str, contenido: str, nivel_amenaza: str) -> str:
    """Sintetiza un resumen determinista basado en extracción sintáctica."""
    oraciones = [o.strip() for o in re.split(r"[.!?]", contenido) if len(o.strip()) > 15]
    resumen_extraido = " ".join(oraciones[:2]) if oraciones else contenido[:200]
    return f"[{nivel_amenaza}] {titulo}. {resumen_extraido}."


def generar_recomendaciones_tácticas(nivel_amenaza: str, actores: List[str]) -> List[str]:
    """Genera recomendaciones operativas predefinidas según la matriz de riesgo."""
    recs = []
    if nivel_amenaza in ("CRÍTICA", "ALTA"):
        recs.append("Activar protocolo de monitoreo intensivo de fuentes en tiempo real.")
        recs.append("Notificar al puesto de mando sobre posible escalada o evento en curso.")
    else:
        recs.append("Mantener seguimiento rutinario de la fuente y verificar actualizaciones.")

    if any(a in ["FANB", "Fuerzas Armadas", "SEBIN", "DGCIM"] for a in actores):
        recs.append("Verificar comunicados oficiales de los cuerpos de seguridad.")

    return recs


def procesar_entrada_determinista(titulo: str, contenido: str, fuente: str = "OSINT") -> Dict[str, Any]:
    """Procesa un evento o noticia determinísticamente (sin IA) produciendo un reporte estructurado JSON."""
    nivel, score = calcular_score_amenaza(titulo, contenido)
    actores = extraer_actores_clave(f"{titulo} {contenido}")
    resumen = generar_resumen_determinista(titulo, contenido, nivel)
    recomendaciones = generar_recomendaciones_tácticas(nivel, actores)

    return {
        "id_analisis": f"ANALYSIS-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "nivel_amenaza": nivel,
        "score_amenaza": score,
        "actores": actores,
        "resumen_ejecutivo": resumen,
        "recomendaciones": recomendaciones,
        "metadatos_fuente": {
            "fuente": fuente,
            "confiabilidad_estimada": SOURCE_RELIABILITY.get(fuente.lower(), 0.5),
        },
    }


def procesar_lote_determinista(entradas: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Procesa un conjunto masivo de noticias ordenándolas por nivel de riesgo."""
    procesados = []
    for item in entradas:
        titulo = item.get("titulo", item.get("title", ""))
        contenido = item.get("contenido", item.get("summary", ""))
        fuente = item.get("fuente", item.get("source", "OSINT"))

        analisis = procesar_entrada_determinista(titulo, contenido, fuente)
        item_resultado = dict(item)
        item_resultado["analisis_determinista"] = analisis
        procesados.append(item_resultado)

    # Ordenar por score de amenaza descendente
    procesados.sort(key=lambda x: x["analisis_determinista"]["score_amenaza"], reverse=True)
    return procesados
