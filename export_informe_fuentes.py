"""export_informe_fuentes.py - Capa de orígenes de datos del informe OSINT.

Portado de 'Ollama_Interfaz_Windows CON REPORTE/fuente_datos.py' al pipeline
Cobalto. Mantiene el patrón multifuente con failover (BaseOrigen + OrigenCompuesto)
e incorpora un origen nativo que lee el contexto del dashboard de Cobalto.
"""

import json
import os
import sqlite3
from dataclasses import dataclass, field

from export_informe_osint import Documento, InformeData, datos_ejemplo


@dataclass
class ResultadoCarga:
    datos: InformeData
    origen: str = "ejemplo"
    resumen: str = ""
    errores: list = field(default_factory=list)


class BaseOrigen:
    nombre = "base"

    def cargar(self) -> ResultadoCarga:
        raise NotImplementedError


def _a_float(valor, por_defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return por_defecto


def _a_int(valor, por_defecto=0):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return por_defecto


def _doc_desde_fila(fila):
    return Documento(
        doc_num=str(fila.get("doc_num", "")) or str(fila.get("numero", "")) or str(fila.get("id", "")),
        titulo=fila.get("titulo", "") or fila.get("title", ""),
        fuente=fila.get("fuente", "") or fila.get("source", ""),
        score_sentimiento=_a_float(fila.get("score_sentimiento", 0.0) or fila.get("sentiment_score", 0.0)),
        url=fila.get("url", "") or fila.get("link", ""),
        analisis=fila.get("analisis", "") or fila.get("analisis_inteligencia", "") or fila.get("analysis", ""),
        contenido=fila.get("contenido", "") or fila.get("contenido_completo", "") or fila.get("summary", ""),
    )


def _filtrar_informe(base):
    permitidos = set(InformeData.__dataclass_fields__)
    return {k: v for k, v in base.items() if k in permitidos}


class OrigenContexto(BaseOrigen):
    """Lee las entradas directamente del contexto del dashboard Cobalto."""
    nombre = "contexto"

    def __init__(self, entries=None, max_docs=20):
        self.entries = entries or []
        self.max_docs = max_docs

    def cargar(self) -> ResultadoCarga:
        from export_informe_osint import build_informe_desde_entries

        info = build_informe_desde_entries(self.entries, max_docs=self.max_docs)
        return ResultadoCarga(
            datos=info, origen=self.nombre,
            resumen=f"Contexto COBALTO: {len(self.entries)} entradas del dashboard "
                    f"({self.max_docs} documentadas).",
        )


class OrigenJSON(BaseOrigen):
    nombre = "json"
    DEFAULT = "datos_informe.json"

    def __init__(self, ruta=DEFAULT):
        self.ruta = os.path.abspath(ruta or self.DEFAULT)

    def cargar(self) -> ResultadoCarga:
        if not os.path.isfile(self.ruta):
            raise FileNotFoundError(f"JSON no encontrado: {self.ruta}")
        with open(self.ruta, "r", encoding="utf-8") as f:
            raw = json.load(f)
        datos = InformeData.from_dict(_filtrar_informe(raw))
        return ResultadoCarga(datos=datos, origen=self.nombre,
                              resumen=f"JSON: {os.path.basename(self.ruta)} "
                                      f"({len(datos.documentos)} documentos).")


class OrigenSQL(BaseOrigen):
    nombre = "sqlite"

    def __init__(self, ruta=None, tabla="entries", tabla_meta=None):
        self.ruta = os.path.abspath(ruta or "cobalto_cache.db")
        self.tabla = tabla
        self.tabla_meta = tabla_meta

    def cargar(self) -> ResultadoCarga:
        if not os.path.isfile(self.ruta):
            raise FileNotFoundError(f"Base SQLite no encontrada: {self.ruta}")
        try:
            conn = sqlite3.connect(self.ruta)
        except sqlite3.Error as ex:
            raise RuntimeError(f"SQLite no disponible: {ex}")
        try:
            cur = conn.cursor()
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({self.tabla})").fetchall()]
            filas = [dict(zip(cols, r)) for r in cur.execute(
                f"SELECT * FROM {self.tabla} ORDER BY published DESC LIMIT 1000").fetchall()]
        except sqlite3.Error as ex:
            raise RuntimeError(f"SQLite: no se pudo leer {self.tabla}: {ex}")
        finally:
            conn.close()

        datos = InformeData.from_dict({"documentos": [_doc_desde_fila(f) for f in filas]})
        return ResultadoCarga(datos=datos, origen=self.nombre,
                              resumen=f"SQLite: {os.path.basename(self.ruta)}/{self.tabla} "
                                      f"({len(datos.documentos)} documentos).")


class OrigenEjemplo(BaseOrigen):
    nombre = "ejemplo"

    def cargar(self) -> ResultadoCarga:
        return ResultadoCarga(datos=datos_ejemplo(), origen=self.nombre,
                              resumen="Modo de ejemplo (datos incrustados).")


class OrigenCompuesto(BaseOrigen):
    def __init__(self, origenes, fallback=True):
        self.origenes = origenes
        self.fallback = fallback

    def cargar(self) -> ResultadoCarga:
        errores = []
        for origen in self.origenes:
            try:
                resultado = origen.cargar()
                resultado.errores = errores
                if resultado.datos.documentos:
                    return resultado
            except Exception as ex:
                errores.append(f"[{origen.nombre}] {str(ex)}")
        if self.fallback:
            resultado = OrigenEjemplo().cargar()
            resultado.errores = errores
            resultado.resumen = "Fallback a ejemplo. " + "; ".join(errores)
            return resultado
        raise RuntimeError("Sin datos disponibles: " + "; ".join(errores))


def cargar_informe(entries=None, max_docs=20, config=None) -> ResultadoCarga:
    """Carga los datos del informe con failover: contexto Cobalto → SQLite → JSON → ejemplo."""
    origenes = []
    if entries:
        origenes.append(OrigenContexto(entries, max_docs=max_docs))
    if config:
        cfg = config
    else:
        cfg = os.environ.get("COBALTO_CACHE_DB", "cobalto_cache.db")
    if isinstance(cfg, str):
        sqlite_path = cfg
    else:
        sqlite_path = "cobalto_cache.db"
    origenes.append(OrigenSQL(sqlite_path))
    origenes.append(OrigenJSON("datos_informe.json"))
    compuesto = OrigenCompuesto(origenes, fallback=True)
    return compuesto.cargar()


if __name__ == "__main__":
    r = cargar_informe()
    print(f"Origen: {r.origen}")
    print(r.resumen)
    for e in r.errores:
        print("  !", e)
    print("Documentos:", len(r.datos.documentos))
