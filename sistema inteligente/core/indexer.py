"""
Módulo de Indexación — Motor de Búsqueda Full-Text
====================================================
Utiliza SQLite FTS5 (nativo, sin dependencias extra) para construir
un índice invertido sobre corpus de documentos .txt, .pdf y .docx.

Uso:
    from core.indexer import Indexer
    idx = Indexer("data/corpus.db")
    idx.ingest_directory("data/docs/")
    resultados = idx.search("inteligencia artificial")
"""

import sqlite3
import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


# ── Lectores de formato ───────────────────────────────────────────────────────

def _read_txt(path: str) -> str:
    """Lee un archivo .txt con detección básica de codificación."""
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return ""


def _read_pdf(path: str) -> str:
    """Extrae texto de un PDF usando PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        return "\n".join(page.get_text() for page in doc)
    except ImportError:
        print("[WARN] PyMuPDF no instalado. Instala con: pip install PyMuPDF")
        return ""
    except Exception as e:
        print(f"[WARN] No se pudo leer PDF {path}: {e}")
        return ""


def _read_docx(path: str) -> str:
    """Extrae texto de un .docx usando python-docx."""
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        print("[WARN] python-docx no instalado. Instala con: pip install python-docx")
        return ""
    except Exception as e:
        print(f"[WARN] No se pudo leer DOCX {path}: {e}")
        return ""


READERS = {
    ".txt":  _read_txt,
    ".pdf":  _read_pdf,
    ".docx": _read_docx,
    ".md":   _read_txt,
}


# ── Clase principal ───────────────────────────────────────────────────────────

class Indexer:
    """
    Motor de indexación y búsqueda Full-Text sobre SQLite FTS5.

    Atributos:
        db_path (str): Ruta al archivo de base de datos SQLite.
    """

    CREATE_DOCS_SQL = """
        CREATE TABLE IF NOT EXISTS documentos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT NOT NULL,
            ruta        TEXT UNIQUE NOT NULL,
            extension   TEXT,
            tamanio_kb  REAL,
            ingresado   TEXT DEFAULT (datetime('now')),
            contenido   TEXT
        )
    """

    CREATE_FTS_SQL = """
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts
        USING fts5(
            nombre,
            contenido,
            content='documentos',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
    """

    CREATE_TRIGGER_INSERT = """
        CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON documentos BEGIN
            INSERT INTO docs_fts(rowid, nombre, contenido)
            VALUES (new.id, new.nombre, new.contenido);
        END
    """

    CREATE_TRIGGER_DELETE = """
        CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON documentos BEGIN
            INSERT INTO docs_fts(docs_fts, rowid, nombre, contenido)
            VALUES ('delete', old.id, old.nombre, old.contenido);
        END
    """

    def __init__(self, db_path: str = "data/sistema.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Crea las tablas y el índice FTS5 si no existen."""
        with self._get_conn() as conn:
            conn.execute(self.CREATE_DOCS_SQL)
            conn.execute(self.CREATE_FTS_SQL)
            conn.execute(self.CREATE_TRIGGER_INSERT)
            conn.execute(self.CREATE_TRIGGER_DELETE)
            conn.commit()

    def ingest_file(self, path: str) -> Optional[int]:
        """
        Ingesta un único archivo al índice.

        Returns:
            ID del documento insertado, o None si ya existía o no es soportado.
        """
        p = Path(path)
        ext = p.suffix.lower()
        if ext not in READERS:
            return None

        reader = READERS[ext]
        contenido = reader(str(p))
        if not contenido.strip():
            print(f"[SKIP] Sin contenido: {p.name}")
            return None

        tamanio = p.stat().st_size / 1024

        try:
            with self._get_conn() as conn:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO documentos
                       (nombre, ruta, extension, tamanio_kb, contenido)
                       VALUES (?, ?, ?, ?, ?)""",
                    (p.name, str(p.resolve()), ext, round(tamanio, 2), contenido)
                )
                conn.commit()
                if cur.rowcount == 0:
                    return None  # Ya existía
                return cur.lastrowid
        except sqlite3.Error as e:
            print(f"[ERROR] No se pudo indexar {p.name}: {e}")
            return None

    def ingest_directory(self, directory: str, recursive: bool = True) -> Dict[str, int]:
        """
        Ingesta todos los documentos soportados de un directorio.

        Returns:
            Diccionario con conteos: {'nuevos': N, 'omitidos': M, 'errores': K}
        """
        stats = {"nuevos": 0, "omitidos": 0, "errores": 0}
        d = Path(directory)
        if not d.exists():
            print(f"[ERROR] Directorio no encontrado: {directory}")
            return stats

        pattern = "**/*" if recursive else "*"
        files = [f for f in d.glob(pattern) if f.is_file() and f.suffix.lower() in READERS]

        for f in files:
            result = self.ingest_file(str(f))
            if result is None:
                stats["omitidos"] += 1
            else:
                stats["nuevos"] += 1
            print(f"  [{'OK' if result else '--'}] {f.name}")

        return stats

    def search(self, query: str, limit: int = 20, snippet_len: int = 64) -> List[Dict]:
        """
        Realiza una búsqueda Full-Text sobre el índice.

        Args:
            query: Términos de búsqueda (soporta operadores: AND, OR, NOT, "frase exacta")
            limit: Número máximo de resultados
            snippet_len: Longitud del fragmento de contexto en caracteres

        Returns:
            Lista de dicts con: id, nombre, ruta, score, snippet
        """
        results = []
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """SELECT
                           d.id, d.nombre, d.ruta, d.extension, d.ingresado,
                           snippet(docs_fts, 1, '[', ']', '...', ?) AS fragmento,
                           rank AS score
                       FROM docs_fts
                       JOIN documentos d ON docs_fts.rowid = d.id
                       WHERE docs_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (snippet_len // 4, query, limit)
                ).fetchall()

                for row in rows:
                    results.append(dict(row))
        except sqlite3.OperationalError as e:
            print(f"[ERROR] Búsqueda fallida: {e}")

        return results

    def get_stats(self) -> Dict:
        """Retorna estadísticas del corpus indexado."""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
            by_ext = conn.execute(
                "SELECT extension, COUNT(*) as n, SUM(tamanio_kb) as kb FROM documentos GROUP BY extension"
            ).fetchall()
            return {
                "total_documentos": total,
                "por_extension": [dict(r) for r in by_ext]
            }

    def delete_document(self, doc_id: int) -> bool:
        """Elimina un documento del índice por su ID."""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM documentos WHERE id = ?", (doc_id,))
            conn.commit()
            if cur.rowcount > 0:
                # Reconstruir el índice FTS5 para evitar entradas fantasma
                conn.execute("INSERT INTO docs_fts(docs_fts) VALUES('rebuild')")
                conn.commit()
            return cur.rowcount > 0

    def get_all_documents(self) -> List[Dict]:
        """Retorna todos los documentos completos (para sincronizar KWIC/TFIDF)."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT id, nombre, contenido FROM documentos").fetchall()
            return [dict(r) for r in rows]

    def list_documents(self) -> List[Dict]:
        """Retorna metadatos de todos los documentos (sin el contenido)."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT id, nombre, extension, tamanio_kb, ingresado FROM documentos ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]

    def get_document(self, doc_id: int) -> Optional[Dict]:
        """Retorna un documento específico por su ID."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT id, nombre, contenido FROM documentos WHERE id = ?", (doc_id,)).fetchone()
            return dict(row) if row else None

    def rebuild_index(self):
        """Reconstruye el índice FTS5 desde cero (útil tras actualizaciones masivas)."""
        with self._get_conn() as conn:
            conn.execute("INSERT INTO docs_fts(docs_fts) VALUES('rebuild')")
            conn.commit()
        print("[OK] Índice FTS5 reconstruido.")
