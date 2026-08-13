"""
Módulo Extractor — NLP + Expresiones Regulares
===============================================
Pipeline de procesamiento de lenguaje natural para español.
Extrae entidades estructuradas (fechas, emails, teléfonos, RIF/cédulas,
organizaciones, personas) usando spaCy + Regex.

Uso:
    from core.extractor import Extractor
    ext = Extractor()
    resultado = ext.procesar("Texto del documento aquí...")
    print(resultado.entidades)
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import Counter


# ── Patrones Regex para entidades venezolanas y generales ────────────────────

PATRONES = {
    # Documentos venezolanos
    "cedula":       r'\b[VEJGPvejgp]-?\d{5,9}\b',
    "rif":          r'\bJ-?\d{8}-?\d\b',
    "rif_ext":      r'\b[JGPCEVjgpcev]-\d{7,9}-\d\b',

    # Contacto
    "email":        r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b',
    "telefono_ve":  r'\b(?:0(?:412|414|416|424|426|212|241|243|251|261|271|281|285|286|288|291|293|295)[\s\-]?\d{7})\b',
    "telefono_int": r'\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{4}',
    "url":          r'https?://[^\s<>"{}|\\^`\[\]]+',

    # Fechas
    "fecha_ddmmaaaa": r'\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b',
    "fecha_texto":    r'\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?\d{4}\b',
    "fecha_iso":      r'\b\d{4}-\d{2}-\d{2}\b',

    # Financiero
    "monto_bs":     r'Bs\.?\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?',
    "monto_usd":    r'\$\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?',
    "porcentaje":   r'\b\d{1,3}(?:[.,]\d+)?\s*%',

    # Coordenadas GPS
    "coordenadas":  r'\b-?\d{1,3}\.\d{4,},\s*-?\d{1,3}\.\d{4,}\b',

    # Placas venezolanas
    "placa_ve":     r'\b[A-Z]{2,3}\d{1,3}[A-Z]{0,2}\b',
}


# ── Estructuras de datos ──────────────────────────────────────────────────────

@dataclass
class Token:
    texto: str
    lema: str
    pos: str          # Parte del discurso: NOUN, VERB, ADJ, etc.
    es_stopword: bool

@dataclass
class Entidad:
    texto: str
    tipo: str         # PERSON, ORG, LOC, cedula, email, fecha, etc.
    inicio: int
    fin: int
    fuente: str       # 'spacy' o 'regex'

@dataclass
class ResultadoNLP:
    texto_original: str
    tokens: List[Token] = field(default_factory=list)
    entidades: List[Entidad] = field(default_factory=list)
    oraciones: List[str] = field(default_factory=list)
    frecuencias: Dict[str, int] = field(default_factory=dict)
    lemas_limpios: List[str] = field(default_factory=list)

    def entidades_por_tipo(self) -> Dict[str, List[str]]:
        resultado = {}
        for e in self.entidades:
            resultado.setdefault(e.tipo, []).append(e.texto)
        # Deduplicar
        return {k: list(dict.fromkeys(v)) for k, v in resultado.items()}


# ── Clase principal ───────────────────────────────────────────────────────────

class Extractor:
    """
    Pipeline NLP para español usando spaCy + Regex.
    Si spaCy no está disponible, opera en modo solo-Regex.
    """

    def __init__(self, modelo_spacy: str = "es_core_news_lg"):
        self.nlp = None
        self.modelo_cargado = None
        self._cargar_spacy(modelo_spacy)

    def _cargar_spacy(self, modelo: str):
        """Carga el modelo spaCy, descargando si es necesario."""
        try:
            import spacy
            try:
                self.nlp = spacy.load(modelo)
                self.modelo_cargado = modelo
                print(f"[OK] spaCy cargado: {modelo}")
            except OSError:
                print(f"[INFO] Modelo '{modelo}' no encontrado. Intentando 'es_core_news_sm'...")
                try:
                    self.nlp = spacy.load("es_core_news_sm")
                    self.modelo_cargado = "es_core_news_sm"
                    print("[OK] spaCy cargado: es_core_news_sm")
                except OSError:
                    print("[WARN] No hay modelo spaCy en español. Solo Regex activo.")
                    print("       Ejecuta: python -m spacy download es_core_news_sm")
        except ImportError:
            print("[WARN] spaCy no instalado. Solo Regex activo.")

    def _extraer_regex(self, texto: str) -> List[Entidad]:
        """Extrae entidades con todos los patrones Regex definidos."""
        entidades = []
        for tipo, patron in PATRONES.items():
            for match in re.finditer(patron, texto, re.IGNORECASE):
                entidades.append(Entidad(
                    texto=match.group().strip(),
                    tipo=tipo,
                    inicio=match.start(),
                    fin=match.end(),
                    fuente="regex"
                ))
        return entidades

    def _extraer_spacy(self, doc) -> Tuple[List[Token], List[Entidad], List[str]]:
        """Extrae tokens, entidades y oraciones con spaCy."""
        tokens = []
        for t in doc:
            if not t.is_space:
                tokens.append(Token(
                    texto=t.text,
                    lema=t.lemma_.lower(),
                    pos=t.pos_,
                    es_stopword=t.is_stop
                ))

        entidades = []
        for ent in doc.ents:
            entidades.append(Entidad(
                texto=ent.text,
                tipo=ent.label_,
                inicio=ent.start_char,
                fin=ent.end_char,
                fuente="spacy"
            ))

        oraciones = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        return tokens, entidades, oraciones

    def procesar(self, texto: str) -> ResultadoNLP:
        """
        Procesa un texto completo y retorna todas las extracciones.

        Args:
            texto: Texto a analizar

        Returns:
            ResultadoNLP con tokens, entidades, oraciones y frecuencias
        """
        resultado = ResultadoNLP(texto_original=texto)

        # Extracción con Regex (siempre disponible)
        resultado.entidades = self._extraer_regex(texto)

        # Extracción con spaCy (si está disponible)
        if self.nlp:
            doc = self.nlp(texto[:1_000_000])  # Límite de seguridad: 1M chars
            tokens, ents_spacy, oraciones = self._extraer_spacy(doc)
            resultado.tokens = tokens
            resultado.oraciones = oraciones
            resultado.entidades.extend(ents_spacy)

            # Lemas limpios (sin stopwords, solo sustantivos/verbos/adj)
            resultado.lemas_limpios = [
                t.lema for t in tokens
                if not t.es_stopword
                and t.pos in {"NOUN", "VERB", "ADJ", "PROPN"}
                and len(t.lema) > 2
            ]
        else:
            # Tokenización básica sin spaCy
            resultado.lemas_limpios = [
                w.lower() for w in re.findall(r'\b[a-záéíóúñü]{3,}\b', texto, re.IGNORECASE)
            ]

        # Frecuencia de lemas
        resultado.frecuencias = dict(Counter(resultado.lemas_limpios).most_common(50))

        return resultado

    def procesar_por_lotes(self, textos: List[str]) -> List[ResultadoNLP]:
        """Procesa múltiples textos usando el pipeline batch de spaCy."""
        if self.nlp:
            resultados = []
            for doc in self.nlp.pipe(textos, batch_size=32):
                r = ResultadoNLP(texto_original=doc.text)
                r.entidades = self._extraer_regex(doc.text)
                tokens, ents_spacy, oraciones = self._extraer_spacy(doc)
                r.tokens = tokens
                r.oraciones = oraciones
                r.entidades.extend(ents_spacy)
                r.lemas_limpios = [
                    t.lema for t in tokens
                    if not t.es_stopword and t.pos in {"NOUN", "VERB", "ADJ", "PROPN"} and len(t.lema) > 2
                ]
                r.frecuencias = dict(Counter(r.lemas_limpios).most_common(50))
                resultados.append(r)
            return resultados
        else:
            return [self.procesar(t) for t in textos]

    def agregar_patron(self, nombre: str, patron_regex: str):
        """Agrega un patrón Regex personalizado en tiempo de ejecución."""
        PATRONES[nombre] = patron_regex
        print(f"[OK] Patrón '{nombre}' agregado.")
