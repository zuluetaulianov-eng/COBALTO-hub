"""
Módulo de Concordancia — Visor KWIC
=====================================
Muestra una palabra o frase en su contexto exacto (Key Word In Context)
a lo largo de uno o múltiples documentos. Análisis de colocaciones
(qué palabras aparecen juntas) y patrones de uso.

Uso:
    from core.concordance import Concordance
    kwic = Concordance(textos, ids)
    resultados = kwic.buscar("inteligencia", ventana=5)
    colocaciones = kwic.colocaciones("inteligencia", top_n=10)
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict


# ── Estructuras ───────────────────────────────────────────────────────────────

@dataclass
class LineaKWIC:
    """Una ocurrencia de la palabra buscada con su contexto."""
    doc_id: str
    doc_nombre: str
    n_linea: int
    contexto_izq: str   # Palabras a la izquierda
    termino: str        # El término exacto encontrado
    contexto_der: str   # Palabras a la derecha
    linea_completa: str


@dataclass
class ResultadoConcordancia:
    termino_buscado: str
    total_ocurrencias: int
    documentos_afectados: int
    lineas: List[LineaKWIC] = field(default_factory=list)

    def to_tabla(self) -> List[Dict]:
        """Convierte a lista de dicts para fácil serialización."""
        return [
            {
                "doc": l.doc_id,
                "nombre": l.doc_nombre,
                "linea": l.n_linea,
                "izquierda": l.contexto_izq,
                "termino": l.termino,
                "derecha": l.contexto_der,
            }
            for l in self.lineas
        ]


# ── Clase principal ───────────────────────────────────────────────────────────

class Concordance:
    """
    Motor KWIC (Key Word In Context) para análisis de corpus.

    Carga un corpus de documentos y permite:
    - Buscar una palabra/frase con contexto configurable
    - Analizar colocaciones (palabras vecinas frecuentes)
    - Calcular frecuencia de distribución por documento
    - Detectar patrones N-grama
    """

    def __init__(self, textos: List[str] = None, ids: List[str] = None,
                 nombres: List[str] = None):
        """
        Args:
            textos: Lista de textos del corpus
            ids: Identificadores para cada texto (ej: ruta del archivo)
            nombres: Nombres amigables para cada texto
        """
        self._corpus: List[Dict] = []  # [{id, nombre, tokens, lineas}]
        if textos:
            self.cargar_corpus(textos, ids, nombres)

    def cargar_corpus(self, textos: List[str], ids: List[str] = None,
                      nombres: List[str] = None):
        """Carga o reemplaza el corpus actual."""
        self._corpus = []
        for i, texto in enumerate(textos):
            doc_id = (ids[i] if ids else f"doc_{i}")
            doc_nombre = (nombres[i] if nombres else doc_id)
            self._corpus.append({
                "id": doc_id,
                "nombre": doc_nombre,
                "tokens": self._tokenizar(texto),
                "lineas": texto.splitlines(),
            })
        print(f"[OK] Corpus cargado: {len(self._corpus)} documentos.")

    def agregar_documento(self, texto: str, doc_id: str, nombre: str = None):
        """Agrega un documento al corpus existente."""
        self._corpus.append({
            "id": doc_id,
            "nombre": nombre or doc_id,
            "tokens": self._tokenizar(texto),
            "lineas": texto.splitlines(),
        })

    def _tokenizar(self, texto: str) -> List[str]:
        """Tokenización simple, preservando posición."""
        return re.findall(r'\b\w+\b', texto.lower())

    def buscar(self, termino: str, ventana: int = 5,
               regex: bool = False, limite: int = 500) -> ResultadoConcordancia:
        """
        Búsqueda KWIC: muestra el término en contexto en todo el corpus.

        Args:
            termino: Palabra o frase a buscar
            ventana: Número de palabras a mostrar a cada lado
            regex: Si True, trata el término como expresión regular
            limite: Máximo de resultados a retornar

        Returns:
            ResultadoConcordancia con todas las ocurrencias
        """
        if regex:
            patron = re.compile(termino, re.IGNORECASE)
        else:
            patron = re.compile(r'\b' + re.escape(termino) + r'\b', re.IGNORECASE)

        lineas_kwic = []
        docs_afectados = set()
        total = 0

        for doc in self._corpus:
            tokens = doc["tokens"]
            lineas_texto = doc["lineas"]

            # Buscar en texto línea por línea para obtener n° de línea
            for n_linea, linea in enumerate(lineas_texto, 1):
                for match in patron.finditer(linea):
                    if total >= limite:
                        break

                    # Extraer contexto basado en tokens de la línea
                    tokens_linea = re.findall(r'\b\w+\b', linea)
                    match_words = re.findall(r'\b\w+\b', match.group())
                    match_lower = [w.lower() for w in match_words]

                    # Encontrar posición del match en los tokens de la línea
                    pos = None
                    tl_lower = [t.lower() for t in tokens_linea]
                    for idx in range(len(tl_lower) - len(match_lower) + 1):
                        if tl_lower[idx:idx+len(match_lower)] == match_lower:
                            pos = idx
                            break

                    if pos is not None:
                        izq = " ".join(tokens_linea[max(0, pos-ventana):pos])
                        der_start = pos + len(match_lower)
                        der = " ".join(tokens_linea[der_start:der_start+ventana])
                    else:
                        # Contexto por caracteres
                        start = max(0, match.start() - ventana * 7)
                        end = min(len(linea), match.end() + ventana * 7)
                        izq = linea[start:match.start()].strip()
                        der = linea[match.end():end].strip()

                    lineas_kwic.append(LineaKWIC(
                        doc_id=doc["id"],
                        doc_nombre=doc["nombre"],
                        n_linea=n_linea,
                        contexto_izq=izq[-60:],   # Máx 60 chars a la izquierda
                        termino=match.group(),
                        contexto_der=der[:60],    # Máx 60 chars a la derecha
                        linea_completa=linea.strip()
                    ))
                    docs_afectados.add(doc["id"])
                    total += 1

        return ResultadoConcordancia(
            termino_buscado=termino,
            total_ocurrencias=total,
            documentos_afectados=len(docs_afectados),
            lineas=lineas_kwic
        )

    def colocaciones(self, termino: str, ventana: int = 3,
                     top_n: int = 20) -> List[Tuple[str, int]]:
        """
        Analiza qué palabras aparecen más frecuentemente junto al término.

        Args:
            termino: Palabra central del análisis
            ventana: Cuántas palabras alrededor considerar
            top_n: Top N colocaciones a retornar

        Returns:
            Lista de (palabra_vecina, frecuencia)
        """
        patron = re.compile(r'\b' + re.escape(termino.lower()) + r'\b')
        vecinos = Counter()
        stopwords_basicas = {
            "de", "la", "el", "en", "y", "a", "los", "las", "un", "una",
            "por", "con", "para", "que", "se", "del", "al", "su", "sus"
        }

        for doc in self._corpus:
            tokens = doc["tokens"]
            for i, token in enumerate(tokens):
                if patron.match(token):
                    inicio = max(0, i - ventana)
                    fin = min(len(tokens), i + ventana + 1)
                    contexto = tokens[inicio:i] + tokens[i+1:fin]
                    for w in contexto:
                        if w not in stopwords_basicas and len(w) > 2 and w != token:
                            vecinos[w] += 1

        return vecinos.most_common(top_n)

    def distribucion_por_doc(self, termino: str) -> List[Dict]:
        """
        Muestra la frecuencia absoluta y relativa del término por documento.

        Returns:
            Lista de dicts con 'doc_id', 'nombre', 'frecuencia', 'frecuencia_relativa'
        """
        patron = re.compile(r'\b' + re.escape(termino.lower()) + r'\b')
        distribucion = []

        for doc in self._corpus:
            tokens = doc["tokens"]
            frec = sum(1 for t in tokens if patron.match(t))
            frec_rel = frec / len(tokens) if tokens else 0
            distribucion.append({
                "doc_id": doc["id"],
                "nombre": doc["nombre"],
                "frecuencia": frec,
                "frecuencia_relativa": round(frec_rel * 1000, 4),  # por mil
                "total_tokens": len(tokens)
            })

        return sorted(distribucion, key=lambda x: x["frecuencia"], reverse=True)

    def ngramas(self, n: int = 2, top_n: int = 30,
                excluir_stopwords: bool = True) -> List[Tuple[Tuple, int]]:
        """
        Genera los N-gramas más frecuentes en todo el corpus.

        Args:
            n: Tamaño del N-grama (2=bigramas, 3=trigramas)
            top_n: Cuántos N-gramas retornar
            excluir_stopwords: Si True, filtra N-gramas que empiezan/terminan en stopword

        Returns:
            Lista de ((palabra1, palabra2, ...), frecuencia)
        """
        stopwords = {
            "de", "la", "el", "en", "y", "a", "los", "las", "un", "una",
            "por", "con", "para", "que", "se", "del", "al", "su", "sus",
            "es", "son", "como", "pero", "si", "más", "no", "le", "lo"
        }
        contador = Counter()

        for doc in self._corpus:
            tokens = doc["tokens"]
            for i in range(len(tokens) - n + 1):
                ngrama = tuple(tokens[i:i+n])
                if excluir_stopwords:
                    if ngrama[0] in stopwords or ngrama[-1] in stopwords:
                        continue
                if all(len(w) > 2 for w in ngrama):
                    contador[ngrama] += 1

        return contador.most_common(top_n)

    def estadisticas_corpus(self) -> Dict:
        """Retorna métricas generales del corpus cargado."""
        total_tokens = sum(len(d["tokens"]) for d in self._corpus)
        vocab = set()
        for d in self._corpus:
            vocab.update(d["tokens"])

        return {
            "documentos": len(self._corpus),
            "tokens_totales": total_tokens,
            "vocabulario_unico": len(vocab),
            "densidad_lexica": round(len(vocab) / total_tokens, 4) if total_tokens else 0,
            "tokens_promedio_por_doc": round(total_tokens / len(self._corpus), 1) if self._corpus else 0
        }
