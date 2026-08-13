-- Esquema de referencia para la fuente SQLite / PostgreSQL de El Ojo del Coporo.
-- El adaptador SQL lee "documentos"; la tabla "informe_meta" contiene los campos de cabecera.

CREATE TABLE IF NOT EXISTS documentos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_num       TEXT,
    titulo        TEXT NOT NULL,
    fuente        TEXT,
    score_sentimiento REAL DEFAULT 0.0,
    url           TEXT,
    analisis      TEXT,
    contenido     TEXT
);

CREATE TABLE IF NOT EXISTS informe_meta (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT,
    fecha_creacion  TEXT,
    autor           TEXT,
    institucion     TEXT,
    fuente_datos    TEXT,
    fecha_analisis  TEXT,
    total_analizados INTEGER DEFAULT 0,
    doc_con_bot     INTEGER DEFAULT 0,
    nivel_alerta    TEXT DEFAULT 'MONITOREO NORMAL'
);