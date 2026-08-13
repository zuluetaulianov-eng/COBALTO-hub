# osint_fakenews.py - Detector de Fake News y Fact-Checking
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from utils import safe_async_run

FAKE_NEWS_INDICATORS = {
    "extreme_language": [
        "increíble",
        "escándalo",
        "impactante",
        "terrible",
        "horrible",
        "abrumador",
        "sin precedentes",
        "explosivo",
        "revelación",
    ],
    "conspiracy_keywords": [
        "complot",
        "ocultar",
        "libertad",
        "nuevo orden mundial",
        "agenda",
        "control mental",
        "secretos",
        "agentes",
        "manipulación",
    ],
    "unverified_sources": [
        "anonymous",
        "fuentes cercanas",
        "segun rumores",
        "segun dicen",
        "sin confirmar",
        "presuntamente",
        "supuesto",
    ],
    "clickbait_patterns": [
        r"no\s+creerás",
        r"resultado\s+increíble",
        r"todo\s+el\s+mundo",
        r"lo\s+que\s+no\s+te\s+cuenta",
        r"error\s+grave",
        r"fatal",
    ],
}

SUSPICIOUS_DOMAINS = [
    "infociudadano",
    "noticiasaldia",
    "el-pais",
    "venezuelaaldia",
    "aporrea",
    "descifrado",
    "contrapunto",
    "laizquierdadiario",
    "panampost",
    "maduristas",
    "guerrero",
    "venezueladata",
]


def analyze_news_reliability(title: str, summary: str, source: str, link: str = "") -> Dict[str, Any]:
    """Analiza una noticia para detectar posible desinformación."""
    score = 0
    flags = []
    details = []

    text = f"{title} {summary}".lower()

    for indicator, patterns in FAKE_NEWS_INDICATORS.items():
        matches = [p for p in patterns if p.lower() in text]
        if matches:
            if indicator == "extreme_language":
                score += 2
                flags.append("Lenguaje extremo")
            elif indicator == "conspiracy_keywords":
                score += 5
                flags.append("Patrón conspirativo")
            elif indicator == "unverified_sources":
                score += 4
                flags.append("Fuentes no verificadas")
            elif indicator == "clickbait_patterns":
                score += 3
                flags.append("Clickbait detectado")

    source_lower = source.lower()
    for domain in SUSPICIOUS_DOMAINS:
        if domain in source_lower:
            score += 3
            flags.append(f"Dominio sospechoso: {domain}")

    if "maduro" in text or "gobierno" in text:
        score += 1
        details.append("Contenido político sensible")

    if re.search(r"\d{4,}", text):
        score += 1
        details.append("Contiene números (verificar datos)")

    if "video" in text or "imagen" in text:
        details.append("Contenido multimedia - verificar origen")

    reliability = "ALTA"
    if score >= 10:
        reliability = "MUY BAJA"
    elif score >= 7:
        reliability = "BAJA"
    elif score >= 4:
        reliability = "MEDIA"

    return {
        "title": title,
        "source": source,
        "reliability_score": score,
        "reliability_level": reliability,
        "flags": flags,
        "details": details,
        "link": link,
        "analyzed_at": datetime.now().isoformat(),
    }


def analyze_batch_news(entries: List[Dict]) -> List[Dict]:
    """Analiza un lote de noticias para detección de fake news."""
    results = []
    for entry in entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        source = entry.get("source", "")
        link = entry.get("link", "")

        if len(title) < 10:
            continue

        analysis = analyze_news_reliability(title, summary, source, link)
        results.append(analysis)

    results.sort(key=lambda x: x["reliability_score"], reverse=True)
    return results


def get_reliability_summary(analyses: List[Dict]) -> Dict[str, Any]:
    """Genera resumen de confiabilidad del lote de noticias."""
    if not analyses:
        return {"total": 0, "high": 0, "medium": 0, "low": 0}

    summary = {
        "total": len(analyses),
        "high": 0,
        "medium": 0,
        "low": 0,
        "very_low": 0,
        "suspicious_sources": set(),
        "flag_types": {},
    }

    for a in analyses:
        level = a["reliability_level"]
        if level == "ALTA":
            summary["high"] += 1
        elif level == "MEDIA":
            summary["medium"] += 1
        elif level == "BAJA":
            summary["low"] += 1
        elif level == "MUY BAJA":
            summary["very_low"] += 1

        for flag in a["flags"]:
            summary["flag_types"][flag] = summary["flag_types"].get(flag, 0) + 1

    summary["suspicious_sources"] = list(set(a["source"] for a in analyses if a["reliability_score"] >= 7))

    return summary


def check_with_ai(title: str, summary: str) -> str:
    """Usa IA para verificar claims en la noticia (Ollama / Local primero)."""
    import config
    from ai_local import LOCAL_AI_ENABLED, query_local_llm

    prompt = f"""Analiza esta noticia sobre Venezuela y determina si contiene información potencialmente falsa o engañosa.
Solo responde con una palabra: VERIFIED, SUSPICIOUS, o UNVERIFIABLE.

Noticia: {title}
Resumen: {summary[:200]}"""

    if getattr(config, "PREFER_LOCAL_AI", True) or not os.getenv("GROQ_API_KEY"):
        if LOCAL_AI_ENABLED:
            try:
                res = safe_async_run(query_local_llm(prompt, max_tokens=10, temperature=0.1))
                if res:
                    word = res.strip().upper().replace(".", "")
                    for valid in ["VERIFIED", "SUSPICIOUS", "UNVERIFIABLE"]:
                        if valid in word:
                            return valid
            except Exception:
                pass

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "API no configurada"

    try:
        from openai import AsyncOpenAI as AsyncGroq
        client = AsyncGroq(api_key=api_key, base_url="https://integrate.api.nvidia.com/v1")

        response = safe_async_run(
            client.chat.completions.create(
                model=config.AI_MODEL,
                messages=[{"role": "system", "content": prompt}],
                max_tokens=10,
                temperature=0.1,
            )
        )

        result = response.choices[0].message.content.strip().upper()
        return result if result in ["VERIFIED", "SUSPICIOUS", "UNVERIFIABLE"] else "UNKNOWN"

    except Exception as e:
        return f"Error: {str(e)[:50]}"
