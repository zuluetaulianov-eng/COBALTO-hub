import json
import os
import sqlite3
from dataclasses import dataclass, field

from informe_osint import InformeData, Documento


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


NO_CONSOLE = True


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
        doc_num=str(fila.get("doc_num", "")) or str(fila.get("numero", "")),
        titulo=fila.get("titulo", "") or fila.get("title", ""),
        fuente=fila.get("fuente", "") or fila.get("source", ""),
        score_sentimiento=_a_float(fila.get("score_sentimiento", 0.0)),
        url=fila.get("url", ""),
        analisis=fila.get("analisis", "") or fila.get("analisis_inteligencia", ""),
        contenido=fila.get("contenido", "") or fila.get("contenido_completo", ""),
    )


def _filtrar_informe(base):
    permitidos = set(InformeData.__dataclass_fields__)
    return {k: v for k, v in base.items() if k in permitidos}


class OrigenEjemplo(BaseOrigen):
    nombre = "ejemplo"

    def cargar(self) -> ResultadoCarga:
        from informe_osint import datos_ejemplo
        return ResultadoCarga(datos=datos_ejemplo(), origen=self.nombre,
                              resumen="Modo de ejemplo (datos incrustados).")


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


class OrigenSQL(OrigenJSON):
    nombre = "sqlite"

    def __init__(self, ruta=None, tabla_docs="documentos", 
                 tabla_meta="informe_meta"):
        self.ruta = os.path.abspath(ruta or "datos_informe.db")
        self.tabla_docs = tabla_docs
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
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({self.tabla_docs})").fetchall()]
            filas = [dict(zip(cols, r)) for r in cur.execute(
                f"SELECT * FROM {self.tabla_docs}").fetchall()]
            meta = {}
            try:
                mcols = [r[1] for r in cur.execute(f"PRAGMA table_info({self.tabla_meta})").fetchall()]
                mrows = cur.execute(f"SELECT * FROM {self.tabla_meta}").fetchall()
                for dic in (dict(zip(mcols, r)) for r in mrows):
                    meta.update(dic)
            except sqlite3.Error:
                pass
        finally:
            conn.close()

        base = _filtrar_informe(meta)
        base.setdefault("documentos", [_doc_desde_fila(f) for f in filas])
        if "documentos" not in base:
            base["documentos"] = [_doc_desde_fila(f) for f in filas]
        datos = InformeData.from_dict(base)
        return ResultadoCarga(datos=datos, origen=self.nombre,
                              resumen=f"SQLite: {os.path.basename(self.ruta)} "
                                      f"({len(datos.documentos)} documentos).")


class OrigenMongo(BaseOrigen):
    nombre = "mongo"

    def __init__(self, uri="mongodb://localhost:27017", base="el_ojo_coporo",
                 coleccion="documentos", timeout_ms=3000):
        self.uri = uri
        self.base = base
        self.coleccion = coleccion
        self.timeout_ms = timeout_ms

    def cargar(self) -> ResultadoCarga:
        try:
            from pymongo import MongoClient
        except ImportError as ex:
            raise RuntimeError("pymongo no instalado: "
                               "pip install pymongo") from ex
        try:
            client = MongoClient(self.uri,
                                 serverSelectionTimeoutMS=self.timeout_ms)
            db = client[self.base]
            docs = list(db[self.coleccion].find(
                {}, {"_id": 0}).limit(1000))
        except Exception as ex:
            raise RuntimeError(f"MongoDB: {ex}") from ex
        finally:
            try:
                client.close()
            except (UnboundLocalError, NameError):
                pass

        datos = InformeData.from_dict(
            {"documentos": [_doc_desde_fila(d) for d in docs]})
        datos.fuente_datos = self.base + "." + self.coleccion
        datos.fecha_analisis = datos.fecha_analisis or "N/D"
        return ResultadoCarga(datos=datos, origen=self.nombre,
                              resumen=f"MongoDB: {self.base}/{self.coleccion} "
                                      f"({len(docs)} documentos).")


class OrigenPostgres(BaseOrigen):
    nombre = "postgres"

    def __init__(self, conn_info=None, tabla="documentos"):
        self.conn_info = (conn_info or
                          "postgresql://postgres:postgres@localhost:5432/el_ojo_coporo")
        self.tabla = tabla

    def cargar(self) -> ResultadoCarga:
        try:
            import psycopg2
        except ImportError:
            try:
                from psycopg import connect
            except ImportError as ex:
                raise RuntimeError("psycopg2/psycopg no instalado: "
                                   "pip install psycopg2-binary") from ex
            return self._con_psycopg(connect)

        conn = None
        try:
            conn = psycopg2.connect(self.conn_info, connect_timeout=5)
        except Exception as ex:
            raise RuntimeError(f"PostgreSQL: {ex}") from ex
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {self.tabla} LIMIT 1000")
            cols = [d[0] for d in cur.description]
            docs = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            if conn is not None:
                conn.close()

        datos = InformeData.from_dict(
            {"documentos": [_doc_desde_fila(d) for d in docs]})
        datos.fuente_datos = "PostgreSQL: " + self.tabla
        return ResultadoCarga(datos=datos, origen=self.nombre,
                              resumen=f"PostgreSQL: {self.tabla} "
                                      f"({len(docs)} documentos).")

    def _con_psycopg(self, connect):
        try:
            conn = connect(self.conn_info, connect_timeout=5)
        except Exception as ex:
            raise RuntimeError(f"PostgreSQL: {ex}") from ex
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {self.tabla} LIMIT 1000")
            cols = [d[0] for d in cur.description]
            docs = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            if conn is not None:
                conn.close()
        datos = InformeData.from_dict(
            {"documentos": [_doc_desde_fila(d) for d in docs]})
        datos.fuente_datos = "PostgreSQL: " + self.tabla
        return ResultadoCarga(datos=datos, origen=self.nombre,
                              resumen=f"PostgreSQL: {self.tabla} "
                                      f"({len(docs)} documentos).")


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
                return resultado
            except Exception as ex:
                errores.append(f"[{origen.nombre}] {str(ex)}")
        if self.fallback:
            resultado = OrigenEjemplo().cargar()
            resultado.errores = errores
            resultado.resumen = (f"Fallback a ejemplo. Fallo en: "
                                 + "; ".join(errores))
            return resultado
        raise RuntimeError("Sin datos disponibles: " + "; ".join(errores))


CONFIG_DEFAULT = {
    "orden": ["json", "sqlite", "mongo", "postgres", "ejemplo"],
    "json": {"ruta": "datos_informe.json"},
    "sqlite": {"ruta": "datos_informe.db", "tabla_docs": "documentos"},
    "mongo": {"uri": "mongodb://localhost:27017", "base": "el_ojo_coporo",
              "coleccion": "documentos"},
    "postgres": {"conn_info": "postgresql://postgres:postgres@localhost:5432/el_ojo_coporo",
                 "tabla": "documentos"},
    "fallback": True,
}


def construir_origenes(config=None):
    cfg = dict(CONFIG_DEFAULT)
    if isinstance(config, dict):
        cfg.update(config)

    fabrica = {
        "ejemplo": lambda c: OrigenEjemplo(),
        "json": lambda c: OrigenJSON(c.get("ruta", "datos_informe.json")),
        "sqlite": lambda c: OrigenSQL(
            c.get("ruta", "datos_informe.db"),
            c.get("tabla_docs", "documentos"),
            c.get("tabla_meta", "informe_meta")),
        "mongo": lambda c: OrigenMongo(
            c.get("uri", "mongodb://localhost:27017"),
            c.get("base", "el_ojo_coporo"),
            c.get("coleccion", "documentos")),
        "postgres": lambda c: OrigenPostgres(
            c.get("conn_info",
                  "postgresql://postgres:postgres@localhost:5432/el_ojo_coporo"),
            c.get("tabla", "documentos")),
    }

    origenes = []
    for nombre in cfg.get("orden", []):
        if nombre in fabrica:
            origenes.append(fabrica[nombre](cfg.get(nombre, {})))
    return OrigenCompuesto(origenes, fallback=cfg.get("fallback", True))


def cargar_informe(config=None) -> ResultadoCarga:
    try:
        imports_ok = True
        import informe_osint
    except ImportError:
        imports_ok = False
    if not imports_ok:
        raise RuntimeError("No se pudo importar informe_osint")

    return construir_origenes(config).cargar()


def guardar_json(datos: InformeData, ruta="datos_informe.json", indent=2):
    data = datos.to_dict()
    data["total_analizados"] = len(data["documentos"]) or datos.total_analizados
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    return os.path.abspath(ruta)


if __name__ == "__main__":
    r = cargar_informe()
    print(f"Origen: {r.origen}")
    print(r.resumen)
    for e in r.errores:
        print("  !", e)
    if r.errores:
        print("Documentos:", len(r.datos.documentos))