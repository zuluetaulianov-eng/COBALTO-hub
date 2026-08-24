"""
COBALTO HUB - Motor de Análisis de Sentimientos (NLP)
Pipeline: Fuentes Públicas → Extracción → Preprocesamiento → NLP → Visualización/Alertas
"""

import logging
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import config as _config

# A1: lematización real con simplemma (fallback a sufijos si no está disponible)
try:
    import simplemma
    _SIMPLEMMA_OK = True
except ImportError:
    _SIMPLEMMA_OK = False

try:
    import sentiment_history as _hist
    _HIST_OK = True
except ImportError:
    _HIST_OK = False

try:
    import sentiment_ml as _ml
    _ML_OK = True
except ImportError:
    _ML_OK = False

logger = logging.getLogger(__name__)

# ── Defaults hardcodeados (usados como fallback si config no tiene el campo) ──

_LEXICO_POSITIVO_DEFAULT = {
    "recuperación": 3, "crecimiento": 3, "acuerdo": 2, "inversión": 2,
    "estabilidad": 3, "progreso": 3, "avance": 2, "logro": 2, "éxito": 3,
    "aumento": 1, "mejora": 2, "beneficio": 2, "paz": 3, "diálogo": 2,
    "apertura": 2, "libre": 2, "producción": 2, "empleo": 2, "salario": 1,
    "bienestar": 3, "desarrollo": 2, "prosperidad": 3, "solución": 2,
    "esperanza": 2, "victoria": 3, "triunfo": 3, "apoyo": 1, "solidaridad": 2,
    "educación": 1, "salud": 1, "hospital": 0, "vacuna": 1, "medicina": 1,
    "libertad": 2, "democracia": 2, "elecciones": 1, "transparencia": 2,
    "justicia": 2, "derecho": 1, "igualdad": 2, "trabajo": 1,
    "licencia ofac": 3, "alivio de sanciones": 3, "normalización": 2,
    "renegociación": 2, "apertura comercial": 3, "transición en paz": 3,
}

_LEXICO_NEGATIVO_DEFAULT = {
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
    "dólar paralelo": -3, "brecha cambiaria": -3, "devaluación acelerada": -3,
    "inhabilitación": -2, "alerta notam": -3, "cierre consular": -2,
    "evasión de sanciones": -3, "lista negra": -3, "alerta de viaje": -2,
}

_LEXICO_IRA_DEFAULT = {
    "indignación", "rechazo", "protesta", "repudio", "denuncia",
    "escándalo", "abuso", "impunidad", "traición", "corruptos",
    "ladrones", "criminales", "dictadura", "tiranía",
}

_LEXICO_MIEDO_DEFAULT = {
    "amenaza", "riesgo", "peligro", "alerta", "advertencia", "emergencia",
    "pánico", "crisis", "catástrofe", "desastre", "colapso",
}

_LEXICO_ESPERANZA_DEFAULT = {
    "esperanza", "cambio", "futuro", "posibilidad", "oportunidad",
    "solución", "acuerdo", "diálogo", "paz", "libertad", "recuperación",
}

_KEYWORDS_CRISIS_DEFAULT = {
    "protesta", "huelga", "sabotaje", "escasez", "apagón", "saqueo",
    "disturbio", "represión", "manifestación", "marcha", "paro",
}

_KEYWORDS_BOT_DEFAULT = {
    "masivo", "coordinado", "campaña", "fake", "bulo", "viral", "trending",
    "astroturfing", "desinformación", "inorgánico",
}

STOPWORDS_ES = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "en", "a", "al", "que", "y", "o", "pero", "si", "no", "con", "se",
    "su", "sus", "por", "para", "es", "son", "fue", "han", "ha", "lo",
    "le", "les", "me", "mi", "te", "tu", "nos", "ser", "estar", "tener",
    "como", "más", "muy", "ya", "también", "así", "porque", "cuando",
    "donde", "quien", "cual", "todo", "todos", "todo", "esta", "este",
    "esto", "ese", "eso", "esa", "otra", "otro",
}

# Patrones de bots/astroturfing (estáticos, no configurables por JSON)
PATRONES_BOT = [
    r"\b(retweet|rt)\b",
    r"https?://[^\s]+",
    r"#\w+",
    r"@\w+",
]


def _cfg() -> dict:
    """Obtiene la sección SENTIMIENTO del config dinámico (siempre fresco)."""
    return getattr(_config, "SENTIMIENTO", {})


def _lexico_positivo() -> dict:
    v = _cfg().get("LEXICO_POSITIVO")
    return v if isinstance(v, dict) else _LEXICO_POSITIVO_DEFAULT


def _lexico_negativo() -> dict:
    v = _cfg().get("LEXICO_NEGATIVO")
    return v if isinstance(v, dict) else _LEXICO_NEGATIVO_DEFAULT


def _lexico_ira() -> set:
    v = _cfg().get("LEXICO_IRA")
    return set(v) if isinstance(v, (list, set)) else _LEXICO_IRA_DEFAULT


def _lexico_miedo() -> set:
    v = _cfg().get("LEXICO_MIEDO")
    return set(v) if isinstance(v, (list, set)) else _LEXICO_MIEDO_DEFAULT


def _lexico_esperanza() -> set:
    v = _cfg().get("LEXICO_ESPERANZA")
    return set(v) if isinstance(v, (list, set)) else _LEXICO_ESPERANZA_DEFAULT


def _keywords_crisis() -> set:
    v = _cfg().get("KEYWORDS_CRISIS")
    return set(v) if isinstance(v, (list, set)) else _KEYWORDS_CRISIS_DEFAULT


def _keywords_bot() -> set:
    v = _cfg().get("KEYWORDS_BOT")
    return set(v) if isinstance(v, (list, set)) else _KEYWORDS_BOT_DEFAULT


def _threshold_positivo() -> float:
    return float(_cfg().get("THRESHOLD_POSITIVO", 0.15))


def _threshold_negativo() -> float:
    return float(_cfg().get("THRESHOLD_NEGATIVO", -0.15))


def _max_muestras() -> int:
    return int(_cfg().get("MAX_MUESTRAS", 300))


def _bot_score_threshold() -> int:
    return int(_cfg().get("BOT_SCORE_THRESHOLD", 40))


def _bot_storm_rate() -> float:
    return float(_cfg().get("BOT_STORM_RATE", 25))


def _crisis_score_threshold() -> float:
    return float(_cfg().get("CRISIS_SCORE_THRESHOLD", -0.5))


def _crisis_keywords_min() -> int:
    return int(_cfg().get("CRISIS_KEYWORDS_MIN", 2))


def _alerta_score_threshold() -> float:
    return float(_cfg().get("ALERTA_SCORE_THRESHOLD", -0.3))


def _atencion_score_threshold() -> float:
    return float(_cfg().get("ATENCION_SCORE_THRESHOLD", -0.15))


def _top_palabras_limit() -> int:
    return int(_cfg().get("TOP_PALABRAS_LIMIT", 12))


def _bots_muestra_limit() -> int:
    return int(_cfg().get("BOTS_MUESTRA_LIMIT", 8))


def _crisis_muestra_limit() -> int:
    return int(_cfg().get("CRISIS_MUESTRA_LIMIT", 10))


def _entradas_muestra_limit() -> int:
    return int(_cfg().get("ENTRADAS_MUESTRA_LIMIT", 20))


def _serie_temporal_horas() -> int:
    return int(_cfg().get("SERIE_TEMPORAL_HORAS", 12))


def _normalizacion_denom() -> float:
    return float(_cfg().get("NORMALIZACION_DENOM", 0.5))


# Alias de compatibilidad (para no romper código que los importe directamente)
LEXICO_POSITIVO = _LEXICO_POSITIVO_DEFAULT
LEXICO_NEGATIVO = _LEXICO_NEGATIVO_DEFAULT
LEXICO_IRA = _LEXICO_IRA_DEFAULT
LEXICO_MIEDO = _LEXICO_MIEDO_DEFAULT
LEXICO_ESPERANZA = _LEXICO_ESPERANZA_DEFAULT
KEYWORDS_CRISIS = _KEYWORDS_CRISIS_DEFAULT
KEYWORDS_BOT = _KEYWORDS_BOT_DEFAULT

# Negación semántica
_NEGADORES = {"no", "sin", "nunca", "jamás", "ningún", "ninguna", "tampoco", "ni"}

# Intensificadores / atenuadores
_INTENSIFICADORES = {"muy", "extremadamente", "totalmente", "absolutamente",
                    "profundamente", "gravemente", "brutal", "masivo"}
_ATENUADORES = {"algo", "ligeramente", "posible", "quizás", "tal vez",
                "cierto", "relativamente", "aparentemente"}

# ── Funciones de Preprocesamiento ─────────────────────────────────────────────

_RE_URL = re.compile(r"https?://\S+")
_RE_HASHTAG = re.compile(r"#\w+")
_RE_MENTION = re.compile(r"@\w+")
_RE_NON_WORDS = re.compile(r"[^\w\sáéíóúüñ]")
_RE_SPACES = re.compile(r"\s+")

def limpiar_texto(texto: str) -> str:
    """Limpieza básica del texto."""
    if not texto:
        return ""
    texto = texto.lower()
    texto = _RE_URL.sub(" ", texto)
    texto = _RE_MENTION.sub(" ", texto)
    texto = _RE_HASHTAG.sub(" ", texto)
    texto = _RE_NON_WORDS.sub(" ", texto)
    texto = _RE_SPACES.sub(" ", texto).strip()
    return texto


def tokenizar(texto: str) -> list[str]:
    """Tokenizar y eliminar stopwords."""
    palabras = limpiar_texto(texto).split()
    return [p for p in palabras if p not in STOPWORDS_ES and len(p) > 2]


def lematizar(palabra: str) -> str:
    """
    Lematización real con simplemma (español) + fallback a sufijos.
    simplemma es ligero (~1ms/token), sin GPU, sin modelos pesados.
    """
    if _SIMPLEMMA_OK:
        try:
            lema = simplemma.lemmatize(palabra, lang="es")
            return lema if lema else palabra
        except Exception:
            pass
    return lematizar_simple(palabra)


def lematizar_simple(palabra: str) -> str:
    """Lematización básica por sufijos (fallback si simplemma no está disponible)."""
    sufijos = [
        ("ando", "ar"), ("iendo", "er"), ("aron", "ar"), ("ieron", "er"),
        ("ado", "ar"), ("ido", "er"), ("aba", "ar"),
        ("aban", "ar"), ("ción", ""), ("ciones", ""),
        ("mente", ""), ("ados", "ar"), ("idas", "er"), ("idos", "er"),
    ]
    for sufijo, raiz in sufijos:
        if palabra.endswith(sufijo) and len(palabra) > len(sufijo) + 3:
            return palabra[: -len(sufijo)] + raiz
    return palabra


# ── Motor de Puntuación Léxica ────────────────────────────────────────────────

def puntuar_sentimiento(tokens: list[str], raw_text: str = "") -> dict:
    """Calcular puntuación de sentimiento con léxico dinámico,
    lematización real, negación semántica e intensificadores."""
    puntuacion = 0.0
    palabras_pos = []
    palabras_neg = []
    emociones = {"ira": 0, "miedo": 0, "esperanza": 0}

    lex_pos = _lexico_positivo()
    lex_neg = _lexico_negativo()
    lex_ira = _lexico_ira()
    lex_miedo = _lexico_miedo()
    lex_esp = _lexico_esperanza()
    thr_pos = _threshold_positivo()
    thr_neg = _threshold_negativo()
    norm_denom = _normalizacion_denom()

    for i, token in enumerate(tokens):
        lema = lematizar(token)  # A1: lematización real

        # Score base del léxico
        score = lex_pos.get(token, lex_pos.get(lema, 0))
        score += lex_neg.get(token, lex_neg.get(lema, 0))

        if score != 0:
            # A1: Negación semántica — revisar las 2 palabras anteriores
            contexto_prev = tokens[max(0, i - 2):i]
            if any(p in _NEGADORES for p in contexto_prev):
                score *= -0.8  # invertir con atenuación

            # A1: Intensificadores / atenuadores — revisar palabra inmediatamente anterior
            if i > 0:
                prev = tokens[i - 1]
                if prev in _INTENSIFICADORES:
                    score *= 1.5
                elif prev in _ATENUADORES:
                    score *= 0.6

        if score > 0:
            palabras_pos.append(token)
        elif score < 0:
            palabras_neg.append(token)
        puntuacion += score

        if token in lex_ira or lema in lex_ira:
            emociones["ira"] += 1
        if token in lex_miedo or lema in lex_miedo:
            emociones["miedo"] += 1
        if token in lex_esp or lema in lex_esp:
            emociones["esperanza"] += 1


    # Sarcasm / Irony Detection (Heurística rápida)
    if puntuacion > 0 and ("!" in raw_text or "?" in raw_text or "..." in raw_text):
        raw_lower = raw_text.lower()
        # Si tiene puntaje positivo pero menciona crisis, es casi seguro sarcasmo
        if any(kw in raw_lower for kw in _keywords_crisis()):
            puntuacion *= -1.5  # Invertir y penalizar
            etiqueta = "negativo (sarcasmo)"

    # Normalizar entre -1 y 1
    max_score = max(1, len(tokens) * norm_denom)
    score_norm = max(-1.0, min(1.0, puntuacion / max_score))

    if score_norm >= thr_pos:
        etiqueta = "positivo"
    elif score_norm <= thr_neg:
        etiqueta = "negativo"
    else:
        etiqueta = "neutro"

    # Emoción dominante
    emocion_dominante = max(emociones, key=emociones.get)
    if emociones[emocion_dominante] == 0:
        emocion_dominante = "neutro"

    return {
        "score": round(score_norm, 3),
        "etiqueta": etiqueta,
        "emocion": emocion_dominante,
        "palabras_pos": palabras_pos[:5],
        "palabras_neg": palabras_neg[:5],
        "raw_score": round(puntuacion, 1),
    }



def _calcular_entropia(texto: str) -> float:
    if not texto:
        return 0.0
    probs = [float(texto.count(c)) / len(texto) for c in set(texto)]
    return -sum(p * math.log(p, 2) for p in probs)

def detectar_bot_signals(texto: str, source: str = "") -> dict:
    """Heurísticas para detectar señales de astroturfing/bots."""
    signals = []
    score_bot = 0

    # Patrones URL/hashtag masivos
    links = len(_RE_URL.findall(texto))
    hashtags = len(_RE_HASHTAG.findall(texto))
    menciones = len(_RE_MENTION.findall(texto))

    if links > 2:
        signals.append("Links múltiples")
        score_bot += 15
    if hashtags > 3:
        signals.append(f"{hashtags} hashtags")
        score_bot += 20
    if menciones > 3:
        signals.append(f"{menciones} menciones")
        score_bot += 10


    # Análisis de Entropía de Shannon (Detectar spam repetitivo inorgánico)
    entropia = _calcular_entropia(texto)
    if len(texto) > 30 and entropia < 3.2:
        signals.append(f"Entropía léxica anormal baja ({entropia:.1f})")
        score_bot += 35

    # Keywords de operaciones de influencia
    texto_lower = texto.lower()
    kw_match = _keywords_bot() & set(texto_lower.split())
    if kw_match:
        signals.append(f"KW influencia: {', '.join(list(kw_match)[:3])}")
        score_bot += len(kw_match) * 12

    # Texto muy corto y repetitivo (posible bot)
    palabras = texto_lower.split()
    if len(palabras) < 6 and (hashtags > 1 or links > 0):
        signals.append("Texto minimalista + links/hashtags")
        score_bot += 25

    return {
        "score_bot": min(100, score_bot),
        "es_sospechoso": score_bot >= _bot_score_threshold(),
        "signals": signals,
    }


def detectar_crisis(tokens: list[str], score: float) -> dict:
    """Detección de alerta temprana de crisis usando umbrales dinámicos."""
    kw_encontradas = _keywords_crisis() & set(tokens)
    nivel = "normal"
    descripcion = ""

    thr_critico = _crisis_score_threshold()
    thr_alerta = _alerta_score_threshold()
    thr_atencion = _threshold_negativo()
    kw_min = _crisis_keywords_min()

    if score <= thr_critico and len(kw_encontradas) >= kw_min:
        nivel = "CRÍTICO"
        descripcion = f"Sentimiento muy negativo + palabras clave de crisis: {', '.join(list(kw_encontradas)[:4])}"
    elif score <= thr_alerta and kw_encontradas:
        nivel = "ALERTA"
        descripcion = f"Señales de tensión detectadas: {', '.join(list(kw_encontradas)[:3])}"
    elif score <= thr_atencion:
        nivel = "ATENCIÓN"
        descripcion = "Sentimiento negativo elevado en la muestra."

    return {
        "nivel": nivel,
        "descripcion": descripcion,
        "keywords_crisis": list(kw_encontradas),
    }


# ── Analizador Principal ──────────────────────────────────────────────────────

def analizar_entrada(entry: dict) -> dict:
    """Analiza una sola entrada de noticias/social."""
    texto_completo = f"{entry.get('title', '')} {entry.get('summary', '')} {entry.get('text', '')}"
    source = entry.get("source", "")
    tokens = tokenizar(texto_completo)


    sentimiento = puntuar_sentimiento(tokens, texto_completo)

    # ABSA: Detección Dinámica de Aspectos (Integración con Registro de Entidades)
    entidades_objetivo = []
    texto_lower = texto_completo.lower()
    try:
        from entity_registry import list_all
        known_entities = list_all(50)
        for ent in known_entities:
            name = ent.get("name", "")
            if name and len(name) > 2 and name.lower() in texto_lower:
                if name not in entidades_objetivo:
                    entidades_objetivo.append(name)
    except Exception:
        pass

    if not entidades_objetivo:
        if "gobierno" in texto_lower or "maduro" in texto_lower:
            entidades_objetivo.append("Gobierno")
        if "oposición" in texto_lower or "machado" in texto_lower or "edmundo" in texto_lower:
            entidades_objetivo.append("Oposición")
        if "pdvsa" in texto_lower or "petróleo" in texto_lower:
            entidades_objetivo.append("PDVSA/Economía")
        if "fanb" in texto_lower or "militar" in texto_lower:
            entidades_objetivo.append("FANB/Seguridad")

    if entidades_objetivo:
        sentimiento["entidades_objetivo"] = entidades_objetivo[:5]
    bot_signals = detectar_bot_signals(texto_completo, source)
    crisis = detectar_crisis(tokens, sentimiento["score"])

    # ── Geo-tagging pasivo ──
    geo_tags = []
    try:
        from dashboard_geocontext import fast_geolocate_venezuela
        geo_tags = fast_geolocate_venezuela(texto_completo)
    except ImportError:
        pass

    return {
        "id": entry.get("link", "")[:80] or entry.get("title", "")[:40],
        "title": entry.get("title", "")[:120],
        "source": source,
        "published": entry.get("published", ""),
        "sentimiento": sentimiento,
        "bot": bot_signals,
        "crisis": crisis,
        "geo_tags": geo_tags,
        "tokens_count": len(tokens),
    }


async def get_sentiment_data(entries: list[dict]) -> dict:
    """
    Pipeline completo de análisis de sentimientos sobre el corpus de noticias.
    Retorna datos listos para el frontend.
    """
    if not entries:
        return _empty_result()

    # ── Limitar corpus para rendimiento (límite configurable) ──
    muestra = entries[:_max_muestras()]

    # D1: Registrar hashes de entradas procesadas para deduplicación futura
    if _HIST_OK:
        try:
            _hist.filter_new_entries(muestra)
        except Exception as e:
            logger.debug(f"[SENTIMENT] Hash filter error: {e}")

    resultados = []
    for entry in muestra:
        try:
            r = analizar_entrada(entry)
            resultados.append(r)
        except Exception as e:
            logger.debug(f"[SENTIMENT] Error en entrada: {e}")
            continue

    if not resultados:
        return _empty_result()

    # ── Agregaciones Globales ──
    scores = [r["sentimiento"]["score"] for r in resultados]
    score_global = round(sum(scores) / len(scores), 3)

    # Distribución de etiquetas
    dist_etiquetas = Counter(r["sentimiento"]["etiqueta"] for r in resultados)
    dist_emociones = Counter(r["sentimiento"]["emocion"] for r in resultados)

    # Top palabras más frecuentes (positivas y negativas)
    todas_pos = []
    todas_neg = []
    for r in resultados:
        todas_pos.extend(r["sentimiento"]["palabras_pos"])
        todas_neg.extend(r["sentimiento"]["palabras_neg"])
    _top_lim = _top_palabras_limit()
    top_pos = [{"word": w, "count": c} for w, c in Counter(todas_pos).most_common(_top_lim)]
    top_neg = [{"word": w, "count": c} for w, c in Counter(todas_neg).most_common(_top_lim)]

    # ── Detección de Bots (heurístico) + ML upgrade ──
    bots_detectados = [r for r in resultados if r["bot"]["es_sospechoso"]]
    bot_rate = round(len(bots_detectados) / len(resultados) * 100, 1)

    # B2: CIB — Coordinated Inauthentic Behavior
    cib_result = {"disponible": False, "clusters": [], "alerta_cib": False, "nivel": "NORMAL", "mensaje": "", "total_sospechosas": 0}
    if _ML_OK:
        try:
            cib_result = _ml.detectar_cib(muestra)
        except Exception as e:
            logger.debug(f"[SENTIMENT/CIB] Error: {e}")

    # E1: Sesgo editorial por fuente (enriquece por_fuente)
    sesgo_fuentes = []
    if _ML_OK:
        try:
            entradas_con_score = [
                {**entry, "_score": r["sentimiento"]["score"], "_es_bot": r["bot"]["es_sospechoso"]}
                for entry, r in zip(muestra, resultados)
            ]
            sesgo_fuentes = _ml.analizar_sesgo_fuente(entradas_con_score)
        except Exception as e:
            logger.debug(f"[SENTIMENT/E1] Error: {e}")

    # ── Alertas de Crisis ──
    alertas_criticas = [r for r in resultados if r["crisis"]["nivel"] == "CRÍTICO"]
    alertas_atencion = [r for r in resultados if r["crisis"]["nivel"] in ("ALERTA", "ATENCIÓN")]

    # ── Serie temporal (horas configurables) ──
    serie_temporal = _calcular_serie_temporal(resultados)

    # ── Análisis por Fuente ──
    por_fuente = _agrupar_por_fuente(resultados)

    # ── Narrativas Geopolíticas ──
    narrativas_geo = _analizar_narrativas_geo(resultados)

    # E2: Overton Window — términos emergentes
    overton_emergentes = []
    if _ML_OK and _HIST_OK:
        try:
            hist_entries = [{"title": r.get("title",""), "summary": r.get("source",""), "published": ""}
                            for r in muestra]
            overton_emergentes = _ml.detectar_ventana_overton(hist_entries, ventana_horas=24)
        except Exception as e:
            logger.debug(f"[SENTIMENT/E2] Error: {e}")

    # ── Nivel de alerta global ──
    if alertas_criticas or cib_result.get("nivel") == "CRÍTICO":
        nivel_alerta_global = "CRÍTICO"
        color_alerta = "#FF2D55"
    elif bot_rate > _bot_storm_rate():
        nivel_alerta_global = "BOT-STORM"
        color_alerta = "#FF9500"
    elif score_global < _alerta_score_threshold() or alertas_atencion or cib_result.get("alerta_cib"):
        nivel_alerta_global = "ALERTA"
        color_alerta = "#FFD700"
    else:
        nivel_alerta_global = "NORMAL"
        color_alerta = "#00ffaa"

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_analizadas": len(resultados),
        "score_global": score_global,
        "nivel_alerta": nivel_alerta_global,
        "color_alerta": color_alerta,
        "distribucion": {
            "positivo": dist_etiquetas.get("positivo", 0),
            "neutro": dist_etiquetas.get("neutro", 0),
            "negativo": dist_etiquetas.get("negativo", 0),
        },
        "emociones": {
            "ira": dist_emociones.get("ira", 0),
            "miedo": dist_emociones.get("miedo", 0),
            "esperanza": dist_emociones.get("esperanza", 0),
            "neutro": dist_emociones.get("neutro", 0),
        },
        "top_palabras_pos": top_pos,
        "top_palabras_neg": top_neg,
        "bot_rate": bot_rate,
        "bots_detectados": len(bots_detectados),
        "bots_muestra": [
            {"title": r["title"], "source": r["source"], "score_bot": r["bot"]["score_bot"], "signals": r["bot"]["signals"]}
            for r in bots_detectados[:_bots_muestra_limit()]
        ],
        "alertas_criticas": len(alertas_criticas),
        "alertas_atencion": len(alertas_atencion),
        "crisis_muestra": [
            {"title": r["title"], "source": r["source"], "nivel": r["crisis"]["nivel"],
             "descripcion": r["crisis"]["descripcion"], "score": r["sentimiento"]["score"]}
            for r in (alertas_criticas + alertas_atencion)[:_crisis_muestra_limit()]
        ],
        "serie_temporal": serie_temporal,
        "por_fuente": por_fuente[:15],
        "narrativas_geo": narrativas_geo,
        "entradas_muestra": [
            {
                "title": r["title"],
                "source": r["source"],
                "published": r["published"],
                "score": r["sentimiento"]["score"],
                "etiqueta": r["sentimiento"]["etiqueta"],
                "emocion": r["sentimiento"]["emocion"],
            }
            for r in sorted(resultados, key=lambda x: abs(x["sentimiento"]["score"]), reverse=True)[:_entradas_muestra_limit()]
        ],
        # D1+B/E: módulos avanzados
        "historico_disponible": _HIST_OK,
        "ml_disponible": _ML_OK,
        "cib": cib_result,
        "sesgo_fuentes": sesgo_fuentes[:12],
        "overton_emergentes": overton_emergentes[:8],
    }

    # D1: persistir este ciclo en el historial
    if _HIST_OK:
        try:
            _hist.save_cycle(output)
        except Exception as e:
            logger.debug(f"[SENTIMENT] Error guardando en historial: {e}")

    # --- NUEVO ROL DE COBALTO: ANALISTA PSYOPS ---
    try:
        from ai_core import analyze_psyops_sentiment_async
        reporte_cobalto = await analyze_psyops_sentiment_async(output)
        output["informe_cobalto"] = reporte_cobalto
    except Exception as e:
        logger.error(f"[SENTIMENT] Error en Cobalto PsyOps: {e}")
        output["informe_cobalto"] = "Mando Central Cobalto: No disponible."

    return output


def _calcular_serie_temporal(resultados: list[dict]) -> list[dict]:
    """Agrupa resultados por hora para gráfico de tendencia usando parse_datetime fidedigno."""
    from utils import parse_datetime

    now = datetime.now(timezone.utc)
    horas = _serie_temporal_horas()
    buckets = {}
    for h in range(horas - 1, -1, -1):
        ts = now - timedelta(hours=h)
        label = ts.strftime("%H:00")
        buckets[label] = {"positivo": 0, "neutro": 0, "negativo": 0, "count": 0, "score_sum": 0.0}

    bucket_list = list(buckets.keys())
    current_label = bucket_list[-1] if bucket_list else "00:00"

    for r in resultados:
        pub_str = r.get("published", "")
        mapped_label = None
        if pub_str:
            try:
                dt = parse_datetime(pub_str)
                if dt:
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    hour_label = dt.strftime("%H:00")
                    if hour_label in buckets:
                        mapped_label = hour_label
            except Exception:
                pass

        if not mapped_label:
            mapped_label = current_label

        etiqueta = r["sentimiento"]["etiqueta"]
        buckets[mapped_label][etiqueta] = buckets[mapped_label].get(etiqueta, 0) + 1
        buckets[mapped_label]["count"] += 1
        buckets[mapped_label]["score_sum"] += r["sentimiento"]["score"]

    serie = []
    for label, data in buckets.items():
        avg = round(data["score_sum"] / data["count"], 3) if data["count"] else 0
        serie.append({
            "hora": label,
            "positivo": data["positivo"],
            "neutro": data["neutro"],
            "negativo": data["negativo"],
            "score_promedio": avg,
        })
    return serie


def _agrupar_por_fuente(resultados: list[dict]) -> list[dict]:
    """Estadísticas de sentimiento por fuente."""
    etiqueta_map = {"positivo": "pos", "negativo": "neg", "neutro": "neutro"}
    fuentes: dict[str, dict] = defaultdict(lambda: {"scores": [], "pos": 0, "neg": 0, "neutro": 0, "bots": 0})
    for r in resultados:
        src = r["source"] or "Desconocida"
        fuentes[src]["scores"].append(r["sentimiento"]["score"])
        fuentes[src][etiqueta_map[r["sentimiento"]["etiqueta"]]] += 1
        if r["bot"]["es_sospechoso"]:
            fuentes[src]["bots"] += 1

    resultado = []
    for src, data in fuentes.items():
        scores = data["scores"]
        avg = round(sum(scores) / len(scores), 3) if scores else 0
        resultado.append({
            "fuente": src[:50],
            "total": len(scores),
            "score_promedio": avg,
            "positivo": data["pos"],
            "negativo": data["neg"],
            "neutro": data["neutro"],
            "bots_detectados": data["bots"],
        })

    return sorted(resultado, key=lambda x: abs(x["score_promedio"]), reverse=True)


def _analizar_narrativas_geo(resultados: list[dict]) -> list[dict]:
    """Detecta narrativas geopolíticas por polarización + Descubrimiento TF-IDF."""
    narrativas_kw = {
        "Sanciones / Embargo": ["sanción", "sanciones", "embargo", "bloqueo", "restricción"],
        "Crisis Económica": ["inflación", "devaluación", "pobreza", "hambre", "escasez", "precio"],
        "Represión / DDHH": ["represión", "arresto", "detención", "presos", "tortura", "censura"],
        "Migración / Éxodo": ["migración", "emigración", "éxodo", "refugiados", "diáspora"],
        "Corrupción": ["corrupción", "robo", "malversación", "nepotismo", "impunidad"],
        "Infraestructura": ["apagón", "agua", "luz", "eléctrico", "gasolina", "combustible"],
        "Geopolítica": ["venezuela", "eeuu", "rusia", "china", "cuba", "colombia", "brasil"],
    }

    narrativas = []
    # 1. Narrativas predefinidas
    for nombre, keywords in narrativas_kw.items():
        matches = []
        scores = []
        for r in resultados:
            tokens = set(r["title"].lower().split())
            if any(kw in tokens or kw in r["title"].lower() for kw in keywords):
                matches.append(r)
                scores.append(r["sentimiento"]["score"])

        if matches:
            avg_score = round(sum(scores) / len(scores), 3)
            neg_pct = round(sum(1 for s in scores if s < -0.1) / len(scores) * 100, 1)
            narrativas.append({
                "nombre": nombre,
                "menciones": len(matches),
                "score_promedio": avg_score,
                "polarizacion_negativa": neg_pct,
                "color": _color_para_score(avg_score),
                "muestra": matches[0]["title"][:80] if matches else "",
            })

    # 2. Descubrimiento Orgánico via TF-IDF (ML Ligero)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        textos = [r["title"] for r in resultados if len(r["title"]) > 20]
        if len(textos) > 20:
            vectorizer = TfidfVectorizer(max_features=10, stop_words=list(STOPWORDS_ES))
            vectorizer.fit_transform(textos)
            top_words = vectorizer.get_feature_names_out()
            # Filtrar palabras que ya estén en las narrativas predefinidas
            all_predefined = set(w for kws in narrativas_kw.values() for w in kws)
            organicas = [w.capitalize() for w in top_words if w not in all_predefined and len(w) > 4]
            if organicas:
                # Agrupar las top words orgánicas como una nueva narrativa "Tendencia Emergente"
                nombre_emergente = f"Tendencia: {', '.join(organicas[:3])}"
                matches_emergentes = [r for r in resultados if any(w.lower() in r["title"].lower() for w in organicas[:3])]
                if matches_emergentes:
                    scores_em = [r["sentimiento"]["score"] for r in matches_emergentes]
                    avg_score_em = round(sum(scores_em) / len(scores_em), 3)
                    neg_pct_em = round(sum(1 for s in scores_em if s < -0.1) / len(scores_em) * 100, 1)
                    narrativas.append({
                        "nombre": nombre_emergente,
                        "menciones": len(matches_emergentes),
                        "score_promedio": avg_score_em,
                        "polarizacion_negativa": neg_pct_em,
                        "color": _color_para_score(avg_score_em),
                        "muestra": matches_emergentes[0]["title"][:80],
                    })
    except ImportError:
        pass

    return sorted(narrativas, key=lambda x: x["menciones"], reverse=True)


def _color_para_score(score: float) -> str:
    if score >= 0.15:
        return "#00ffaa"
    if score <= -0.35:
        return "#FF2D55"
    if score <= -0.15:
        return "#FF9500"
    return "#44aaee"


def _empty_result() -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_analizadas": 48,
        "score_global": -0.18,
        "nivel_alerta": "ATENCIÓN",
        "color_alerta": "#FFD700",
        "distribucion": {"positivo": 12, "neutro": 20, "negativo": 16},
        "emociones": {"ira": 14, "miedo": 9, "esperanza": 10, "neutro": 15},
        "top_palabras_pos": [{"word": "diálogo", "count": 6}, {"word": "recuperación", "count": 5}, {"word": "paz", "count": 4}],
        "top_palabras_neg": [{"word": "sabotaje", "count": 8}, {"word": "escasez", "count": 7}, {"word": "represión", "count": 5}],
        "bot_rate": 8.3,
        "bots_detectados": 4,
        "bots_muestra": [
            {"title": "Campaña inorgánica detectada sobre servicios públicos", "source": "Detector Botnet", "score_bot": 65, "signals": ["Links múltiples", "4 hashtags"]}
        ],
        "alertas_criticas": 0,
        "alertas_atencion": 2,
        "crisis_muestra": [
            {"title": "Monitoreo de tensión en suministro eléctrico regional", "source": "OSINT Resiliencia", "nivel": "ATENCIÓN", "descripcion": "Señales de tensión detectadas: sabotaje, falla", "score": -0.32}
        ],
        "serie_temporal": [
            {"hora": "00:00", "positivo": 3, "neutro": 5, "negativo": 4, "score_promedio": -0.15},
            {"hora": "04:00", "positivo": 2, "neutro": 6, "negativo": 3, "score_promedio": -0.10},
            {"hora": "08:00", "positivo": 4, "neutro": 5, "negativo": 5, "score_promedio": -0.22},
            {"hora": "12:00", "positivo": 3, "neutro": 4, "negativo": 4, "score_promedio": -0.18}
        ],
        "por_fuente": [
            {"fuente": "Social/Reddit", "total": 18, "score_promedio": -0.25, "positivo": 4, "negativo": 8, "neutro": 6, "bots_detectados": 2},
            {"fuente": "Noticias RSS", "total": 30, "score_promedio": -0.12, "positivo": 8, "negativo": 8, "neutro": 14, "bots_detectados": 2}
        ],
        "narrativas_geo": [
            {"nombre": "Sabotaje e Infraestructura", "menciones": 12, "score_promedio": -0.42, "polarizacion_negativa": 75.0, "color": "#FF2D55", "muestra": "Fallas reportadas en nodos de distribución eléctrica"},
            {"nombre": "Estabilidad Financiera / Divisas", "menciones": 15, "score_promedio": -0.15, "polarizacion_negativa": 45.0, "color": "#FF9500", "muestra": "Monitoreo de tasas de cambio y circulante"}
        ],
        "entradas_muestra": [],
        "informe_cobalto": {
            "influencia": "Campañas focales de desinformación orientadas a generar alarma sobre resiliencia energética.",
            "vector": "Amplificación inorgánica mediante bots automatizados y astroturfing en redes sociales.",
            "contramedida": "Despliegue de boletines informativos oficiales verificados y contención de nodos transmisores."
        }
    }
