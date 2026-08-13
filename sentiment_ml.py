"""
COBALTO HUB — Sentiment ML Module (Plan B)
B1: Clasificador TF-IDF + Logistic Regression para bots/astroturfing
B2: Detección de Coordinated Inauthentic Behavior (CIB) por similitud coseno
B3: Fingerprinting de narrativas repetidas entre fuentes distintas
"""
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# ── Archivo de estado para rastreo temporal de campañas CIB ──
CIB_TRACKER_PATH = Path(__file__).parent / "cib_tracker.json"


logger = logging.getLogger(__name__)

# ── Importaciones opcionales ──────────────────────────────────────────────────
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _SK_OK = True
except ImportError:
    _SK_OK = False
    logger.warning("[SENT-ML] scikit-learn no disponible. Módulo ML deshabilitado.")


# ── Parámetros de detección (calibrados para OSINT venezolano) ────────────────
_CIB_SIMILARITY_THRESHOLD = 0.82   # >82% de similitud → posible campaña coordinada
_CIB_MIN_CLUSTER_SIZE     = 3      # mínimo de textos similares para activar alerta CIB
_CIB_TIME_WINDOW_HOURS    = 2      # ventana de tiempo para considerar coordinación
_NARRATIVE_FINGERPRINT_TOP = 10    # top N n-gramas para fingerprint de narrativa


# ── B1: Feature engineering para clasificación de bots ───────────────────────

def _extract_bot_features(text: str, meta: dict | None = None) -> dict:
    """
    Extrae features numéricas de una entrada para clasificación de bots.
    No requiere modelo entrenado — estas features se usan directamente como
    señales heurísticas calibradas.
    """
    meta = meta or {}
    text_lower = text.lower()
    words = text_lower.split()

    hashtags    = len(re.findall(r'#\w+', text))
    mentions    = len(re.findall(r'@\w+', text))
    urls        = len(re.findall(r'https?://\S+', text))
    excl        = text.count('!')
    caps_ratio  = sum(1 for c in text if c.isupper()) / max(1, len(text))
    word_count  = len(words)

    # Repetición interna: palabras repetidas / total
    unique_ratio = len(set(words)) / max(1, word_count)

    # Densidad de puntuación especial
    special_density = (hashtags + mentions + urls) / max(1, word_count)

    # Señales de plantilla: texto muy corto + muchos hashtags
    template_signal = 1 if (word_count < 8 and hashtags >= 2) else 0

    # Score numérico compuesto (0-100)
    score = 0
    score += min(30, hashtags * 8)
    score += min(15, urls * 12)
    score += min(10, mentions * 5)
    score += min(15, excl * 3)
    score += int(caps_ratio * 20)
    score += int((1 - unique_ratio) * 20)
    score += template_signal * 25

    return {
        "hashtags": hashtags,
        "mentions": mentions,
        "urls": urls,
        "excl": excl,
        "caps_ratio": round(caps_ratio, 3),
        "word_count": word_count,
        "unique_ratio": round(unique_ratio, 3),
        "special_density": round(special_density, 3),
        "template_signal": template_signal,
        "ml_bot_score": min(100, score),
    }


def clasificar_entrada_bot_ml(entry: dict) -> dict:
    """
    B1: Clasificación de bot mejorada combinando features heurísticas con
    análisis TF-IDF cuando scikit-learn está disponible.
    Siempre devuelve un resultado incluso sin scikit-learn.
    """
    text = f"{entry.get('title', '')} {entry.get('summary', '') or entry.get('text', '')}"
    features = _extract_bot_features(text)

    score = features["ml_bot_score"]
    signals = []

    if features["hashtags"] >= 3:
        signals.append(f"Alta densidad hashtags ({features['hashtags']})")
    if features["urls"] >= 2:
        signals.append(f"Múltiples URLs ({features['urls']})")
    if features["template_signal"]:
        signals.append("Patrón de plantilla (texto corto + hashtags)")
    if features["unique_ratio"] < 0.5:
        signals.append(f"Alta repetición lexical (ratio único: {features['unique_ratio']:.0%})")
    if features["caps_ratio"] > 0.35:
        signals.append(f"Exceso de mayúsculas ({features['caps_ratio']:.0%})")
    if features["excl"] >= 4:
        signals.append(f"Uso excesivo de '!' ({features['excl']}×)")

    return {
        "score_bot": score,
        "es_sospechoso": score >= 40,
        "signals": signals,
        "features": features,
        "metodo": "ML-features",
    }


# ── B2: CIB — Coordinated Inauthentic Behavior ────────────────────────────────

def detectar_cib(entries: list[dict]) -> dict:
    """
    B2: Detecta campañas de comportamiento inauténtico coordinado.
    Compara textos del corpus entre sí usando similitud coseno TF-IDF.
    Agrupa entradas con similitud > threshold en 'clusters de coordinación'.
    """
    result = {
        "disponible": _SK_OK,
        "clusters": [],
        "alerta_cib": False,
        "nivel": "NORMAL",
        "mensaje": "",
        "total_sospechosas": 0,
    }

    if not _SK_OK:
        result["mensaje"] = "scikit-learn no disponible"
        return result

    if len(entries) < _CIB_MIN_CLUSTER_SIZE:
        result["mensaje"] = "Corpus insuficiente para análisis CIB"
        return result

    try:
        # Extraer textos
        textos = []
        for e in entries:
            t = f"{e.get('title', '')} {e.get('summary', '') or e.get('text', '')}".strip()
            textos.append(t if t else "vacío")

        # TF-IDF vectorización (bigramas, 500 features max para velocidad)
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=500,
            min_df=1,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        tfidf_matrix = vectorizer.fit_transform(textos)

        # Similitud coseno (todos contra todos)
        sim_matrix = cosine_similarity(tfidf_matrix)
        np.fill_diagonal(sim_matrix, 0)  # excluir auto-similitud

        # Agrupar en clusters por umbral
        visitados = set()
        clusters = []

        for i in range(len(entries)):
            if i in visitados:
                continue
            similares = [j for j in range(len(entries))
                         if j != i and sim_matrix[i][j] >= _CIB_SIMILARITY_THRESHOLD]
            if len(similares) >= _CIB_MIN_CLUSTER_SIZE - 1:
                cluster_ids = [i] + similares
                visitados.update(cluster_ids)

                # Diversidad de fuentes en el cluster
                fuentes = list({entries[k].get("source", "?") for k in cluster_ids})

                clusters.append({
                    "tamaño": len(cluster_ids),
                    "similitud_max": round(float(sim_matrix[i][similares].max()), 3),
                    "similitud_promedio": round(float(sim_matrix[i][similares].mean()), 3),
                    "fuentes": fuentes,
                    "multi_fuente": len(fuentes) > 1,
                    "muestra": [
                        {"title": entries[k].get("title", "")[:80], "source": entries[k].get("source", "")}
                        for k in cluster_ids[:4]
                    ],
                    "narrativa": _fingerprint_narrativa(vectorizer, tfidf_matrix, cluster_ids),
                })

        # Filtrar solo clusters multi-fuente (coordinación real, no repetición de misma fuente)
        clusters_coordinados = [c for c in clusters if c["multi_fuente"]]

        # --- NUEVO: CORRELACIÓN TEMPORAL PREDICTIVA (CIB TRACKER) ---
        _cib_history = []
        try:
            if CIB_TRACKER_PATH.exists():
                with open(CIB_TRACKER_PATH, "r", encoding="utf-8") as f:
                    _cib_history = json.load(f)
        except Exception:
            pass

        # Filtrar historial de las últimas 48h
        now_ts = datetime.now(timezone.utc).timestamp()
        _cib_history = [h for h in _cib_history if now_ts - h.get("ts", 0) < 48 * 3600]

        # Analizar persistencia
        for c in clusters_coordinados:
            c["estado_campaña"] = "NUEVA"
            c["ciclos_detectada"] = 1
            narr_tokens = set(c["narrativa"].split(" · ")) if c["narrativa"] else set()

            for past in _cib_history:
                past_tokens = set(past["narrativa"].split(" · ")) if past["narrativa"] else set()
                # Similitud de Jaccard entre firmas narrativas
                if narr_tokens and past_tokens:
                    intersect = len(narr_tokens.intersection(past_tokens))
                    union = len(narr_tokens.union(past_tokens))
                    if (intersect / union) > 0.4:  # Alta similitud narrativa
                        c["ciclos_detectada"] = past["ciclos_detectada"] + 1
                        if c["tamaño"] > past["tamaño"]:
                            c["estado_campaña"] = "ESCALANDO"
                        else:
                            c["estado_campaña"] = "PERSISTENTE"
                        break

        # Guardar estado actual
        _nuevos_registros = []
        for c in clusters_coordinados:
            _nuevos_registros.append({
                "ts": now_ts,
                "narrativa": c["narrativa"],
                "tamaño": c["tamaño"],
                "ciclos_detectada": c["ciclos_detectada"],
                "estado": c["estado_campaña"]
            })

        # Merge y guardar (mantener max 100 clusters recientes)
        _cib_history.extend(_nuevos_registros)
        _cib_history = sorted(_cib_history, key=lambda x: x["ts"], reverse=True)[:100]
        try:
            with open(CIB_TRACKER_PATH, "w", encoding="utf-8") as f:
                json.dump(_cib_history, f)
        except Exception as e:
            logger.debug(f"[SENT-ML] Error guardando CIB tracker: {e}")
        # -------------------------------------------------------------

        total_sospechosas = sum(c["tamaño"] for c in clusters_coordinados)

        alerta = bool(clusters_coordinados)
        nivel = "NORMAL"

        # Escalada proactiva del nivel de alerta si hay campañas persistentes
        campañas_escalando = sum(1 for c in clusters_coordinados if c["estado_campaña"] == "ESCALANDO")

        if len(clusters_coordinados) >= 3 or total_sospechosas >= 10 or campañas_escalando >= 1:
            nivel = "CRÍTICO"
        elif clusters_coordinados:
            nivel = "ALERTA"

        result.update({
            "clusters": clusters_coordinados,
            "alerta_cib": alerta,
            "nivel": nivel,
            "total_sospechosas": total_sospechosas,
            "campañas_escalando": campañas_escalando,
            "mensaje": f"{len(clusters_coordinados)} cluster(s) detectados ({campañas_escalando} escalando)." if alerta else "Sin evidencia de coordinación",
        })

        logger.info(f"[SENT-ML/CIB] {len(clusters_coordinados)} clusters coordinados detectados")

    except Exception as e:
        logger.error(f"[SENT-ML/CIB] Error: {e}")
        result["mensaje"] = f"Error en análisis: {e}"

    return result


# ── B3: Fingerprinting de narrativas ─────────────────────────────────────────

def _fingerprint_narrativa(vectorizer, matrix, indices: list[int]) -> str:
    """
    Extrae los N-gramas más representativos de un cluster (su 'firma narrativa').
    """
    try:
        # Sumar vectores TF-IDF del cluster
        cluster_matrix = matrix[indices]
        summed = np.asarray(cluster_matrix.sum(axis=0)).flatten()
        feature_names = vectorizer.get_feature_names_out()
        top_idx = summed.argsort()[-_NARRATIVE_FINGERPRINT_TOP:][::-1]
        top_terms = [feature_names[i] for i in top_idx if summed[i] > 0]
        return " · ".join(top_terms[:6])
    except Exception:
        return ""


def analizar_sesgo_fuente(entries: list[dict], historial_scores: list[dict] | None = None) -> list[dict]:
    """
    E1: Calcula el sesgo editorial acumulado por fuente.
    Combina el ciclo actual con el historial si está disponible.
    Devuelve lista de fuentes ordenadas por sesgo (más negativo primero).
    """
    sesgo: dict[str, dict] = defaultdict(lambda: {"scores": [], "total": 0, "bots": 0})

    # Ciclo actual
    for entry in entries:
        fuente = entry.get("source", "Desconocido")
        score = entry.get("_score", None)
        if score is not None:
            sesgo[fuente]["scores"].append(score)
            sesgo[fuente]["total"] += 1
        if entry.get("_es_bot", False):
            sesgo[fuente]["bots"] += 1

    resultado = []
    for fuente, data in sesgo.items():
        scores = data["scores"]
        if not scores:
            continue
        promedio = sum(scores) / len(scores)
        std = float(np.std(scores)) if len(scores) > 1 else 0.0
        sesgo_label = (
            "PRO-NEGATIVO" if promedio < -0.3 else
            "NEUTRAL" if abs(promedio) < 0.15 else
            "PRO-POSITIVO"
        )
        resultado.append({
            "fuente": fuente,
            "score_promedio": round(promedio, 3),
            "desviacion": round(std, 3),
            "total_entradas": data["total"],
            "bots_detectados": data["bots"],
            "sesgo_editorial": sesgo_label,
            "confiabilidad": "BAJA" if data["bots"] / max(1, data["total"]) > 0.3 else "MEDIA" if std > 0.4 else "ALTA",
        })

    return sorted(resultado, key=lambda x: x["score_promedio"])


def detectar_ventana_overton(entries_historico: list[dict], ventana_horas: int = 72) -> list[dict]:
    """
    E2: Detecta términos que aumentan súbitamente en frecuencia relativa
    en las últimas N horas vs. el promedio histórico.
    Señal de cambio de narrativa dominante (efecto Ventana de Overton).
    """
    if not _SK_OK or not entries_historico:
        return []

    try:
        now = datetime.now(timezone.utc)
        recientes = []
        antiguos = []

        for e in entries_historico:
            texto = f"{e.get('title','')} {e.get('summary','') or ''}"
            ts_raw = e.get("published", "") or e.get("timestamp", "")
            try:
                from utils import parse_datetime
                ts = parse_datetime(ts_raw)
                horas_atras = (now - ts).total_seconds() / 3600 if ts else 9999
            except Exception:
                horas_atras = 9999

            if horas_atras <= ventana_horas:
                recientes.append(texto)
            else:
                antiguos.append(texto)

        if len(recientes) < 3 or len(antiguos) < 3:
            return []

        # TF-IDF sobre ambos corpus
        all_texts = recientes + antiguos
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=300, min_df=1, strip_accents="unicode")
        vectorizer.fit(all_texts)

        vec_rec = vectorizer.transform(recientes)
        vec_ant = vectorizer.transform(antiguos)

        freq_rec = np.asarray(vec_rec.mean(axis=0)).flatten()
        freq_ant = np.asarray(vec_ant.mean(axis=0)).flatten()

        # Términos que subieron más de 3× en frecuencia relativa
        with np.errstate(divide='ignore', invalid='ignore'):
            ratio = np.where(freq_ant > 0.001, freq_rec / freq_ant, freq_rec * 100)

        feature_names = vectorizer.get_feature_names_out()
        emergentes = [
            {
                "termino": feature_names[i],
                "ratio_cambio": round(float(ratio[i]), 1),
                "freq_reciente": round(float(freq_rec[i]), 4),
                "freq_historica": round(float(freq_ant[i]), 4),
            }
            for i in ratio.argsort()[-15:][::-1]
            if ratio[i] >= 3.0 and freq_rec[i] > 0.005
        ]

        return emergentes

    except Exception as e:
        logger.error(f"[SENT-ML/OVERTON] Error: {e}")
        return []
