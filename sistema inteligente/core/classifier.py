"""
Módulo Clasificador — TF-IDF + Bag of Words
============================================
Calcula palabras clave por documento (TF-IDF), entrena clasificadores
de texto (Naive Bayes, Regresión Logística) y agrupa documentos por
similitud sin supervisión (K-Means).

Uso:
    from core.classifier import Classifier
    clf = Classifier()
    clf.fit(corpus)                          # Entrenar sobre corpus
    kw = clf.keywords("El texto aquí...")   # Palabras clave del texto
    cat = clf.predict("El texto aquí...")   # Clasificar en categoría
"""

import re
import os
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize


# ── Stopwords en español (extensión propia) ───────────────────────────────────

STOPWORDS_ES = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las",
    "un", "por", "con", "una", "su", "para", "es", "al", "lo", "como",
    "más", "pero", "sus", "le", "ya", "o", "fue", "este", "ha", "sí",
    "porque", "esta", "son", "entre", "cuando", "muy", "sin", "sobre",
    "ser", "tiene", "también", "me", "hasta", "hay", "donde", "quien",
    "desde", "todo", "nos", "durante", "estado", "todos", "uno", "les",
    "ni", "contra", "otros", "ese", "eso", "ante", "ellos", "e", "esto",
    "mi", "antes", "algunos", "qué", "unos", "yo", "otro", "otras", "él",
    "tanto", "esa", "estos", "mucho", "quienes", "nada", "muchos", "cual",
    "poco", "ella", "estar", "estas", "alguno", "alguna", "siempre", "si",
    "dicho", "no", "ver", "número", "así"
}


def _limpiar(texto: str) -> str:
    """Limpieza básica: minúsculas, sin puntuación, sin números sueltos."""
    texto = texto.lower()
    texto = re.sub(r'https?://\S+', ' ', texto)
    texto = re.sub(r'\b\d+\b', ' ', texto)
    texto = re.sub(r'[^\wáéíóúñü\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


# ── Clase principal ───────────────────────────────────────────────────────────

class Classifier:
    """
    Motor de clasificación y análisis estadístico de texto.
    """

    def __init__(self, max_features: int = 10_000, ngram_range: Tuple = (1, 2)):
        self.max_features = max_features
        self.ngram_range = ngram_range

        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            stop_words=list(STOPWORDS_ES),
            preprocessor=_limpiar,
            min_df=2,
            sublinear_tf=True  # log(1 + tf) en lugar de tf crudo
        )

        self._matrix = None          # Matriz TF-IDF del corpus
        self._corpus_textos = []     # Textos originales del corpus
        self._corpus_ids = []        # IDs/nombres de documentos
        self._clf = None             # Clasificador supervisado
        self._labels = []            # Etiquetas del clasificador
        self._kmeans = None          # Modelo de clustering

    # ── Entrenamiento ─────────────────────────────────────────────────────────

    def fit(self, textos: List[str], ids: Optional[List[str]] = None):
        """
        Entrena el vectorizador TF-IDF sobre el corpus.

        Args:
            textos: Lista de textos del corpus
            ids: Identificadores opcionales para cada texto
        """
        self._corpus_textos = textos
        self._corpus_ids = ids or [f"doc_{i}" for i in range(len(textos))]
        try:
            self._matrix = self.vectorizer.fit_transform(textos)
        except ValueError:
            print("[INFO] Ajustando min_df=1 (muy pocos documentos o términos compartidos)")
            self.vectorizer.set_params(min_df=1)
            self._matrix = self.vectorizer.fit_transform(textos)
            
        print(f"[OK] Vectorizador entrenado sobre {len(textos)} documentos, "
              f"{self._matrix.shape[1]} features.")

    def fit_classifier(self, textos: List[str], etiquetas: List[str],
                       modelo: str = "naive_bayes"):
        """
        Entrena un clasificador supervisado.

        Args:
            textos: Textos de entrenamiento
            etiquetas: Categorías/etiquetas para cada texto
            modelo: 'naive_bayes' o 'logistic'
        """
        try:
            X = self.vectorizer.fit_transform(textos)
        except ValueError:
            self.vectorizer.set_params(min_df=1)
            X = self.vectorizer.fit_transform(textos)
            
        self._labels = list(set(etiquetas))

        if modelo == "logistic":
            self._clf = LogisticRegression(max_iter=1000, C=1.0)
        else:
            self._clf = MultinomialNB(alpha=0.1)

        self._clf.fit(X, etiquetas)
        print(f"[OK] Clasificador '{modelo}' entrenado con {len(self._labels)} clases.")

    def fit_clusters(self, n_clusters: int = 5):
        """
        Agrupa los documentos del corpus en clusters por similitud.

        Args:
            n_clusters: Número de grupos a crear
        """
        if self._matrix is None:
            raise RuntimeError("Llama a fit() primero.")

        X_norm = normalize(self._matrix)
        self._kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self._kmeans.fit(X_norm)
        print(f"[OK] {n_clusters} clusters generados.")

    # ── Inferencia ────────────────────────────────────────────────────────────

    def keywords(self, texto: str, top_n: int = 10) -> List[Tuple[str, float]]:
        """
        Extrae las N palabras clave más importantes de un texto
        usando la puntuación TF-IDF relativa al corpus.

        Returns:
            Lista de tuplas (palabra, score) ordenadas por importancia.
        """
        if self._matrix is None:
            # Sin corpus, usa frecuencia pura
            return self._keywords_sin_corpus(texto, top_n)

        vec = self.vectorizer.transform([texto])
        features = self.vectorizer.get_feature_names_out()
        scores = zip(features, vec.toarray()[0])
        return sorted(
            [(w, round(s, 4)) for w, s in scores if s > 0],
            key=lambda x: x[1], reverse=True
        )[:top_n]

    def _keywords_sin_corpus(self, texto: str, top_n: int) -> List[Tuple[str, float]]:
        """Frecuencia simple cuando no hay corpus entrenado."""
        palabras = _limpiar(texto).split()
        palabras = [p for p in palabras if p not in STOPWORDS_ES and len(p) > 3]
        conteo = {}
        for p in palabras:
            conteo[p] = conteo.get(p, 0) + 1
        total = len(palabras) or 1
        return sorted([(w, round(c / total, 4)) for w, c in conteo.items()],
                      key=lambda x: x[1], reverse=True)[:top_n]

    def predict(self, texto: str) -> Optional[Dict]:
        """
        Clasifica un texto en una categoría.

        Returns:
            Dict con 'categoria', 'confianza' y 'probabilidades'
        """
        if self._clf is None:
            return None

        vec = self.vectorizer.transform([texto])
        categoria = self._clf.predict(vec)[0]
        probas = {}

        if hasattr(self._clf, "predict_proba"):
            proba_vals = self._clf.predict_proba(vec)[0]
            probas = {cls: round(float(p), 4)
                      for cls, p in zip(self._clf.classes_, proba_vals)}

        return {
            "categoria": categoria,
            "confianza": round(float(max(probas.values(), default=0)), 4),
            "probabilidades": probas
        }

    def similares(self, texto: str, top_n: int = 5) -> List[Dict]:
        """
        Encuentra los documentos más similares al texto dado en el corpus.

        Returns:
            Lista de dicts con 'id', 'similitud' (0-1)
        """
        if self._matrix is None:
            return []

        vec = self.vectorizer.transform([texto])
        sims = cosine_similarity(vec, self._matrix)[0]
        top_idx = np.argsort(sims)[::-1][:top_n]

        return [
            {"id": self._corpus_ids[i], "similitud": round(float(sims[i]), 4)}
            for i in top_idx if sims[i] > 0
        ]

    def cluster_del_documento(self, texto: str) -> Optional[int]:
        """Retorna el número de cluster al que pertenecería un nuevo texto."""
        if self._kmeans is None:
            return None
        vec = normalize(self.vectorizer.transform([texto]))
        return int(self._kmeans.predict(vec)[0])

    def resumen_clusters(self) -> List[Dict]:
        """
        Retorna los términos más representativos de cada cluster.
        """
        if self._kmeans is None or self._matrix is None:
            return []

        features = self.vectorizer.get_feature_names_out()
        resumen = []
        labels = self._kmeans.labels_
        centers = self._kmeans.cluster_centers_

        for i, centro in enumerate(centers):
            top_terms_idx = centro.argsort()[-10:][::-1]
            docs_en_cluster = sum(1 for l in labels if l == i)
            resumen.append({
                "cluster": i,
                "documentos": docs_en_cluster,
                "terminos_clave": [features[j] for j in top_terms_idx]
            })
        return resumen

    # ── Persistencia ─────────────────────────────────────────────────────────

    def guardar(self, path: str = "data/classifier.pkl"):
        """Guarda el modelo completo en disco."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "vectorizer": self.vectorizer,
                "matrix": self._matrix,
                "corpus_ids": self._corpus_ids,
                "clf": self._clf,
                "labels": self._labels,
                "kmeans": self._kmeans,
            }, f)
        print(f"[OK] Modelo guardado en {path}")

    def cargar(self, path: str = "data/classifier.pkl"):
        """Carga un modelo previamente guardado."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.vectorizer = data["vectorizer"]
        self._matrix = data["matrix"]
        self._corpus_ids = data["corpus_ids"]
        self._clf = data["clf"]
        self._labels = data["labels"]
        self._kmeans = data["kmeans"]
        print(f"[OK] Modelo cargado desde {path}")
