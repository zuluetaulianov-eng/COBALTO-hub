import os
from contextlib import asynccontextmanager

import aiosqlite

from backend.models.osint import OsintEntry, OsintSearchParams

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "osint.db")
_init_done = False

@asynccontextmanager
async def _get_conn():
    async with aiosqlite.connect(_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn

async def _seed(conn: aiosqlite.Connection):
    seed_data = [
        ("CIBERSEGURIDAD", "Filtración masiva de credenciales en servidor gubernamental",
         "17JUN2026", "https://darkweb.monitor/leak-gob-2026",
         "Se detectó la publicación de 20,000 registros clasificados pertenecientes a infraestructura de red nacional.",
         "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=500&q=80",
         "Captura de pantalla de la publicación en foro"),
        ("GEOPOLÍTICA", "Movimientos irregulares cerca de zona fronteriza",
         "16JUN2026", "https://sat-intel.net/border-anomaly",
         "Imágenes satelitales revelan despliegue no autorizado de equipo táctico pesado en las coordenadas marcadas.",
         "https://images.unsplash.com/photo-1574390666992-069a3baae412?w=500&q=80",
         "Toma satelital con zoom a las coordenadas"),
        ("FINANCIERO", "Transacciones anómalas vinculadas a cartera sancionada",
         "15JUN2026", "https://chain-tracker.io/tx/88921a",
         "Análisis de blockchain expone lavado de activos digitales mediante mezcladores no regulados.",
         "", ""),
        ("CIBERSEGURIDAD", "Campaña de phishing contra infraestructura crítica",
         "14JUN2026", "https://threat-intel.io/phish-campaign-2026",
         "Se identificaron 150 dominios maliciosos suplantando entidades gubernamentales para robo de credenciales.",
         "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=500&q=80",
         "Panel de control de la campaña detectada"),
        ("GEOPOLÍTICA", "Despliegue naval no reportado en aguas en disputa",
         "13JUN2026", "https://maritime-tracker.org/naval-anomaly",
         "Imágenes SAR muestran 3 embarcaciones de guerra en coordenadas no autorizadas dentro de la ZEE.",
         "", ""),
        ("FINANCIERO", "Movimiento sospechoso de stablecoins por USD 50M",
         "12JUN2026", "https://chain-tracker.io/tx/large-50m",
         "Billetera vinculada a exchange sancionado movió 50M USDT a través de 3 puentes cross-chain.",
         "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=500&q=80",
         "Gráfico de flujo de transacciones"),
    ]
    await conn.executemany(
        "INSERT INTO osint_entries (tag, titulo, fecha, urlPortal, textoSituacion, imagenUrl, imagenDesc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        seed_data,
    )
    await conn.execute("INSERT INTO osint_fts(osint_fts) VALUES('rebuild')")
    await conn.commit()

async def _init_db():
    async with _get_conn() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS osint_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag TEXT NOT NULL,
                titulo TEXT NOT NULL,
                fecha TEXT NOT NULL,
                urlPortal TEXT NOT NULL,
                textoSituacion TEXT NOT NULL,
                imagenUrl TEXT DEFAULT '',
                imagenDesc TEXT DEFAULT ''
            )
            """
        )
        await conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS osint_fts USING fts5(
                titulo, textoSituacion, content='osint_entries', content_rowid='id'
            )
            """
        )
        await conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS osint_ai AFTER INSERT ON osint_entries BEGIN
          INSERT INTO osint_fts(rowid, titulo, textoSituacion) VALUES (new.id, new.titulo, new.textoSituacion);
        END;
        CREATE TRIGGER IF NOT EXISTS osint_ad AFTER DELETE ON osint_entries BEGIN
          INSERT INTO osint_fts(osint_fts, rowid, titulo, textoSituacion) VALUES('delete', old.id, old.titulo, old.textoSituacion);
        END;
        CREATE TRIGGER IF NOT EXISTS osint_au AFTER UPDATE ON osint_entries BEGIN
          INSERT INTO osint_fts(osint_fts, rowid, titulo, textoSituacion) VALUES('delete', old.id, old.titulo, old.textoSituacion);
          INSERT INTO osint_fts(rowid, titulo, textoSituacion) VALUES (new.id, new.titulo, new.textoSituacion);
        END;
        """)
        await conn.commit()

        async with conn.execute("SELECT COUNT(*) FROM osint_entries") as cursor:
            count = (await cursor.fetchone())[0]

        if count == 0:
            await _seed(conn)

async def ensure_init_async():
    global _init_done
    if not _init_done:
        await _init_db()
        _init_done = True

def ensure_init():
    pass

async def listar_entradas(params: OsintSearchParams) -> list[OsintEntry]:
    await ensure_init_async()
    where_clauses = []
    bindings = []

    if params.q:
        base_sql = "SELECT e.* FROM osint_entries e JOIN osint_fts f ON e.id = f.rowid"
        where_clauses.append("f.osint_fts MATCH ?")

        import re
        q_clean = re.sub(r'[\"\^\-\*\(\)\[\]\{\}]', '', params.q).strip()
        match_query = ' OR '.join(f'"{word}*"' for word in q_clean.split() if word)
        if not match_query:
            match_query = '""'
        bindings.append(match_query)
    else:
        base_sql = "SELECT * FROM osint_entries e"

    if params.tag:
        where_clauses.append("e.tag = ?")
        bindings.append(params.tag)

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql = f"{base_sql} {where} ORDER BY e.fecha DESC LIMIT ? OFFSET ?"
    bindings.extend([params.limit, params.offset])

    async with _get_conn() as conn:
        async with conn.execute(sql, bindings) as cursor:
            rows = await cursor.fetchall()
            return [OsintEntry(**dict(r)) for r in rows]

async def contar_entradas(params: OsintSearchParams) -> int:
    await ensure_init_async()
    where_clauses = []
    bindings = []

    if params.q:
        base_sql = "SELECT COUNT(*) FROM osint_entries e JOIN osint_fts f ON e.id = f.rowid"
        where_clauses.append("f.osint_fts MATCH ?")

        import re
        q_clean = re.sub(r'[\"\^\-\*\(\)\[\]\{\}]', '', params.q).strip()
        match_query = ' OR '.join(f'"{word}*"' for word in q_clean.split() if word)
        if not match_query:
            match_query = '""'
        bindings.append(match_query)
    else:
        base_sql = "SELECT COUNT(*) FROM osint_entries e"

    if params.tag:
        where_clauses.append("e.tag = ?")
        bindings.append(params.tag)

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql = f"{base_sql} {where}"

    async with _get_conn() as conn:
        async with conn.execute(sql, bindings) as cursor:
            return (await cursor.fetchone())[0]

async def listar_tags() -> list[str]:
    await ensure_init_async()
    async with _get_conn() as conn:
        async with conn.execute("SELECT DISTINCT tag FROM osint_entries ORDER BY tag") as cursor:
            rows = await cursor.fetchall()
            return [r["tag"] for r in rows]
