"""
API REST — FastAPI
==================
Expone todos los módulos del sistema como endpoints HTTP.
Integrable con COPORO/COBALTO o cualquier frontend.

Inicio:
    uvicorn api:app --reload --port 8100
"""

import os
import sqlite3
import httpx
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# Imports del sistema
from core.indexer import Indexer
from core.extractor import Extractor
from core.classifier import Classifier
from core.concordance import Concordance


# ── Estado global ─────────────────────────────────────────────────────────────

DB_PATH = "data/sistema.db"
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

indexer: Optional[Indexer] = None
extractor: Optional[Extractor] = None
classifier: Optional[Classifier] = None
concordance_engine: Optional[Concordance] = None


import threading
_sync_lock = threading.Lock()

def sincronizar_motores():
    """Sincroniza los documentos de SQLite hacia KWIC y TF-IDF."""
    with _sync_lock:
        print("[SYNC] Sincronizando documentos hacia KWIC y TF-IDF...")
        docs = indexer.get_all_documents()
        if not docs:
            print("[SYNC] Base de datos vacía. KWIC y TF-IDF sin datos hasta primera ingesta.")
            return

        textos = [d["contenido"] for d in docs]
        ids = [str(d["id"]) for d in docs]
        nombres = [d["nombre"] for d in docs]

        concordance_engine.cargar_corpus(textos, ids, nombres)
        
        if len(docs) >= 2:
            classifier.fit(textos, ids)
            if len(docs) >= 5:
                classifier.fit_clusters(min(5, len(docs)))
        print(f"[SYNC] {len(docs)} documentos sincronizados con éxito.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa los módulos al arrancar la API."""
    global indexer, extractor, classifier, concordance_engine
    print("[INICIO] Cargando módulos del Sistema Inteligente...")
    indexer = Indexer(DB_PATH)
    extractor = Extractor()
    classifier = Classifier()
    concordance_engine = Concordance()

    # Cargar clasificador si existe modelo previo (o sincronizar de cero)
    if Path("data/classifier.pkl").exists():
        try:
            classifier.cargar("data/classifier.pkl")
        except Exception:
            pass

    # Sincronizar siempre al arrancar
    try:
        sincronizar_motores()
    except Exception as e:
        print(f"[WARN] Fallo en sincronización inicial: {e}. El corpus arrancará vacío.")

    print("[OK] Sistema listo.")
    yield
    print("[FIN] Sistema detenido.")


# ── Aplicación ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Sistema Inteligente de Análisis de Texto",
    description="Motor determinista: Indexación FTS5 + NLP + TF-IDF + KWIC",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir frontend estático
frontend_dir = Path("frontend")
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory="frontend"), name="static")


# ── Modelos Pydantic ──────────────────────────────────────────────────────────

class TextoInput(BaseModel):
    texto: str
    doc_id: Optional[str] = None

class BusquedaInput(BaseModel):
    query: str
    limite: int = 20

class ConcordanciaInput(BaseModel):
    termino: str
    ventana: int = 5
    regex: bool = False
    limite: int = 200

class ClasificadorEntrenamientoInput(BaseModel):
    textos: List[str]
    etiquetas: List[str]
    modelo: str = "naive_bayes"

class CorpusInput(BaseModel):
    textos: List[str]
    ids: Optional[List[str]] = None
    n_clusters: int = 5


# ── Endpoints: Raíz ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def raiz():
    """Redirige al dashboard si existe, o muestra info básica."""
    html_path = Path("frontend/index.html")
    if html_path.exists():
        return FileResponse(html_path)
    return HTMLResponse("""
    <html><body style='font-family:monospace;padding:2rem;background:#0f172a;color:#94a3b8'>
    <h1 style='color:#38bdf8'>⚡ Sistema Inteligente de Análisis de Texto</h1>
    <p>API activa. Documentación: <a href='/docs' style='color:#818cf8'>/docs</a></p>
    </body></html>
    """)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(content=b"", media_type="image/x-icon")

@app.get("/health")
async def health():
    """Endpoint de verificación de salud del servidor."""
    return {"status": "ok", "sistema": "activo"}

@app.get("/api/estado")
async def estado():
    """Estado del sistema y estadísticas del corpus."""
    stats = indexer.get_stats()
    return {
        "sistema": "activo",
        "version": "1.0.0",
        "corpus": stats,
        "spacy_activo": extractor.nlp is not None,
        "spacy_modelo": extractor.modelo_cargado if extractor.nlp else None,
        "spacy_instruccion": None if extractor.nlp else "Ejecuta: python -m spacy download es_core_news_sm",
        "clasificador_entrenado": classifier._matrix is not None,
        "concordancia_docs": len(concordance_engine._corpus)
    }


# ── Endpoints: Indexación ─────────────────────────────────────────────────────

@app.get("/api/documentos")
async def listar_documentos():
    """Retorna la lista de todos los documentos indexados."""
    docs = indexer.list_documents()
    return {"documentos": docs}

@app.get("/api/documentos/{doc_id}")
async def obtener_documento(doc_id: int):
    """Retorna el contenido completo de un documento por su ID."""
    doc = indexer.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Documento no encontrado.")
    return doc

@app.post("/api/indexar/archivo")
async def indexar_archivo(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Ingesta un archivo al índice (soporta .txt, .pdf, .docx, .md)."""
    ext = Path(file.filename).suffix.lower()
    if ext not in {".txt", ".pdf", ".docx", ".md"}:
        raise HTTPException(400, f"Formato no soportado: {ext}")

    dest = UPLOAD_DIR / Path(file.filename).name
    with open(dest, "wb") as f:
        f.write(await file.read())

    doc_id = indexer.ingest_file(str(dest))
    if doc_id is None:
        return {"status": "omitido", "mensaje": "El archivo ya existía o está vacío."}

    background_tasks.add_task(sincronizar_motores)
    return {"status": "ok", "doc_id": doc_id, "archivo": file.filename}

@app.post("/api/indexar/texto")
async def indexar_texto(background_tasks: BackgroundTasks, data: TextoInput):
    """Ingesta texto plano directamente."""
    import tempfile
    doc_id_str = data.doc_id or f"texto_{hash(data.texto) & 0xFFFF:04x}"
    temp = UPLOAD_DIR / f"{doc_id_str}.txt"
    temp.write_text(data.texto, encoding="utf-8")
    doc_id = indexer.ingest_file(str(temp))
    if doc_id is not None:
        background_tasks.add_task(sincronizar_motores)
    return {"status": "ok", "doc_id": doc_id, "nombre": temp.name}

@app.get("/api/corpus/stats")
async def corpus_stats():
    """Estadísticas del corpus indexado."""
    return indexer.get_stats()

@app.delete("/api/corpus/{doc_id}")
async def eliminar_documento(doc_id: int):
    """Elimina un documento del índice."""
    ok = indexer.delete_document(doc_id)
    if not ok:
        raise HTTPException(404, "Documento no encontrado.")
    return {"status": "eliminado", "doc_id": doc_id}


# ── Endpoints: Búsqueda ───────────────────────────────────────────────────────

@app.post("/api/buscar")
async def buscar(data: BusquedaInput):
    """
    Búsqueda Full-Text con SQLite FTS5.
    Soporta operadores: AND, OR, NOT, "frase exacta", término*
    """
    if not data.query.strip():
        raise HTTPException(400, "La consulta no puede estar vacía.")

    resultados = indexer.search(data.query, limit=data.limite)
    return {
        "query": data.query,
        "total": len(resultados),
        "resultados": resultados
    }

@app.get("/api/buscar")
async def buscar_get(q: str = Query(..., description="Término a buscar"),
                     limite: int = Query(20, ge=1, le=500)):
    """Búsqueda rápida vía GET."""
    resultados = indexer.search(q, limit=limite)
    return {"query": q, "total": len(resultados), "resultados": resultados}


# ── Endpoints: NLP / Extracción ───────────────────────────────────────────────

@app.get("/api/extraer/{doc_id}")
async def extraer_entidades_doc(doc_id: int):
    """Extrae entidades de un documento indexado."""
    doc = indexer.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    
    resultado = extractor.procesar(doc["contenido"])
    return {
        "doc_id": doc_id,
        "nombre": doc["nombre"],
        "entidades": resultado.entidades_por_tipo(),
        "frecuencias": resultado.frecuencias,
        "total_tokens": len(resultado.tokens),
        "total_oraciones": len(resultado.oraciones),
        "lemas_principales": resultado.lemas_limpios[:30]
    }

@app.post("/api/extraer")
async def extraer_entidades(data: TextoInput):
    """
    Extrae entidades del texto: emails, fechas, cédulas, RIF,
    teléfonos, personas, organizaciones, lugares.
    """
    if not data.texto.strip():
        raise HTTPException(400, "Texto vacío.")

    resultado = extractor.procesar(data.texto)
    return {
        "entidades": resultado.entidades_por_tipo(),
        "frecuencias": resultado.frecuencias,
        "total_tokens": len(resultado.tokens),
        "total_oraciones": len(resultado.oraciones),
        "lemas_principales": resultado.lemas_limpios[:30]
    }


# ── Endpoints: TF-IDF / Clasificación ────────────────────────────────────────

@app.get("/api/tfidf/keywords/{doc_id}")
async def extraer_keywords_doc(doc_id: int, top_n: int = Query(15, ge=1, le=50)):
    """Extrae palabras clave de un documento indexado."""
    doc = indexer.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    modo = "tfidf" if classifier._matrix is not None else "frecuencia_simple"
    advertencia = (
        None if classifier._matrix is not None
        else "Corpus insuficiente (se necesitan ≥2 docs). Usando frecuencia pura. Añade más documentos para TF-IDF real."
    )
    keywords = classifier.keywords(doc["contenido"], top_n=top_n)
    return {
        "doc_id": doc_id,
        "nombre": doc["nombre"],
        "modo": modo,
        "advertencia": advertencia,
        "keywords": [{"palabra": w, "score": s} for w, s in keywords]
    }

@app.post("/api/tfidf/keywords")
async def extraer_keywords(data: TextoInput,
                           top_n: int = Query(10, ge=1, le=50)):
    """Extrae las palabras clave más importantes del texto usando TF-IDF."""
    modo = "tfidf" if classifier._matrix is not None else "frecuencia_simple"
    advertencia = (
        None if classifier._matrix is not None
        else "Corpus insuficiente. Usando frecuencia pura. Añade más documentos para TF-IDF real."
    )
    keywords = classifier.keywords(data.texto, top_n=top_n)
    return {
        "texto_chars": len(data.texto),
        "modo": modo,
        "advertencia": advertencia,
        "keywords": [{"palabra": w, "score": s} for w, s in keywords]
    }

@app.post("/api/tfidf/entrenar")
async def entrenar_corpus(data: CorpusInput):
    """Entrena el vectorizador TF-IDF sobre un corpus y genera clusters."""
    if len(data.textos) < 2:
        raise HTTPException(400, "Se necesitan al menos 2 documentos.")

    classifier.fit(data.textos, data.ids)

    if len(data.textos) >= data.n_clusters:
        classifier.fit_clusters(data.n_clusters)
        clusters = classifier.resumen_clusters()
    else:
        clusters = []

    classifier.guardar()
    return {
        "status": "ok",
        "documentos": len(data.textos),
        "features": classifier._matrix.shape[1] if classifier._matrix is not None else 0,
        "clusters": clusters
    }

@app.post("/api/tfidf/clasificar")
async def clasificar_texto(data: TextoInput):
    """Clasifica un texto en la categoría más probable."""
    resultado = classifier.predict(data.texto)
    if resultado is None:
        raise HTTPException(409, "El clasificador no está entrenado. Usa /api/clasificador/entrenar.")
    return resultado

@app.post("/api/tfidf/similares")
async def documentos_similares(data: TextoInput, top_n: int = Query(5)):
    """Encuentra los documentos más similares al texto dado."""
    similares = classifier.similares(data.texto, top_n=top_n)
    return {"similares": similares}

@app.post("/api/clasificador/entrenar")
async def entrenar_clasificador(data: ClasificadorEntrenamientoInput):
    """Entrena un clasificador supervisado (Naive Bayes o Regresión Logística)."""
    if len(data.textos) != len(data.etiquetas):
        raise HTTPException(400, "El número de textos y etiquetas debe coincidir.")

    classifier.fit_classifier(data.textos, data.etiquetas, data.modelo)
    classifier.guardar()
    return {
        "status": "ok",
        "modelo": data.modelo,
        "clases": list(set(data.etiquetas)),
        "ejemplos": len(data.textos)
    }


# ── Endpoints: Concordancia / KWIC ───────────────────────────────────────────

@app.post("/api/concordancia/cargar")
async def cargar_corpus_kwic(data: CorpusInput):
    """Carga un corpus en el motor de concordancia KWIC."""
    concordance_engine.cargar_corpus(data.textos, data.ids)
    stats = concordance_engine.estadisticas_corpus()
    return {"status": "ok", **stats}

@app.post("/api/concordancia/buscar")
async def buscar_kwic(data: ConcordanciaInput):
    """Búsqueda KWIC: muestra el término en su contexto en todo el corpus."""
    if not concordance_engine._corpus:
        raise HTTPException(409, "No hay corpus cargado. Usa /api/concordancia/cargar.")

    resultado = concordance_engine.buscar(
        data.termino, data.ventana, data.regex, data.limite
    )
    return {
        "termino": resultado.termino_buscado,
        "total_ocurrencias": resultado.total_ocurrencias,
        "documentos_afectados": resultado.documentos_afectados,
        "lineas": resultado.to_tabla()
    }

@app.get("/api/concordancia/colocaciones")
async def colocaciones(
    termino: str = Query(...),
    ventana: int = Query(3),
    top_n: int = Query(20)
):
    """Analiza qué palabras aparecen más junto al término dado."""
    if not concordance_engine._corpus:
        raise HTTPException(409, "No hay corpus cargado.")

    cols = concordance_engine.colocaciones(termino, ventana, top_n)
    return {
        "termino": termino,
        "colocaciones": [{"palabra": w, "frecuencia": f} for w, f in cols]
    }

@app.get("/api/concordancia/ngramas")
async def ngramas(
    n: int = Query(2, ge=2, le=5),
    top_n: int = Query(30)
):
    """Retorna los N-gramas más frecuentes del corpus."""
    if not concordance_engine._corpus:
        raise HTTPException(409, "No hay corpus cargado.")

    ngs = concordance_engine.ngramas(n, top_n)
    return {
        "n": n,
        "ngramas": [{"ngrama": " ".join(ng), "frecuencia": f} for ng, f in ngs]
    }

@app.get("/api/concordancia/distribucion")
async def distribucion(termino: str = Query(...)):
    """Frecuencia del término por documento."""
    if not concordance_engine._corpus:
        raise HTTPException(409, "No hay corpus cargado.")
    return {
        "termino": termino,
        "distribucion": concordance_engine.distribucion_por_doc(termino)
    }


# ── Endpoints: IA Generativa (RAG) ───────────────────────────────────────────

# Key NVIDIA: se lee EXCLUSIVAMENTE desde API.txt (nunca hardcodeada).
# El archivo debe contener una línea con la clave en formato nvapi-...
_CLAVE_NVIDIA: Optional[str] = None
_CLAVE_NVIDIA_ERROR: Optional[str] = None


def _cargar_clave_nvidia() -> str:
    """Lee la API key NVIDIA desde API.txt (debe empezar con `nvapi-`)."""
    ruta = Path("API.txt")
    if not ruta.exists():
        raise RuntimeError(
            "No se encontró API.txt. Crea el archivo en la raíz del proyecto y "
            "pega tu clave NVIDIA (formato nvapi-...)."
        )
    contenido = ruta.read_text(encoding="utf-8", errors="ignore")
    for linea in contenido.splitlines():
        clave = linea.strip()
        if clave.startswith("nvapi-") and len(clave) > len("nvapi-"):
            return clave
    raise RuntimeError(
        "API.txt no contiene una clave NVIDIA válida (debe empezar con nvapi-...). "
        "Revisa el archivo y pega tu clave real."
    )


def _clave_nvidia() -> str:
    """Devuelve la clave NVIDIA en caché, levantando un error claro si falta."""
    global _CLAVE_NVIDIA, _CLAVE_NVIDIA_ERROR
    if _CLAVE_NVIDIA is None and _CLAVE_NVIDIA_ERROR is None:
        try:
            _CLAVE_NVIDIA = _cargar_clave_nvidia()
        except RuntimeError as e:
            _CLAVE_NVIDIA_ERROR = str(e)
    if _CLAVE_NVIDIA_ERROR:
        raise RuntimeError(_CLAVE_NVIDIA_ERROR)
    return _CLAVE_NVIDIA

class IAConsultaInput(BaseModel):
    pregunta: str
    limite_contexto: int = 3

@app.post("/api/ia/consultar")
async def consultar_ia(data: IAConsultaInput):
    """
    Pipeline RAG completo:
    1. Busca contexto relevante en FTS5 (determinista)
    2. Envía contexto + pregunta a NVIDIA AI (generativo)
    3. Retorna la respuesta fundamentada
    """
    if not data.pregunta.strip():
        raise HTTPException(400, "La pregunta no puede estar vacía.")

    try:
        nvidia_key = _clave_nvidia()
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    # --- Capa 1: Contexto determinista ---
    resultados = indexer.search(data.pregunta, limit=data.limite_contexto)
    if resultados:
        partes = []
        for doc in resultados:
            frag = doc["fragmento"].replace("[", "").replace("]", "")
            partes.append(f"Documento [{doc['nombre']}]: {frag}")
        contexto = "\n".join(partes)
        contexto_encontrado = True
    else:
        contexto = "No se encontró información específica en la base de datos local."
        contexto_encontrado = False

    # --- Capa 2: IA Generativa (NVIDIA) ---
    prompt_sistema = f"""Eres un analista experto del sistema COPORO/COBALTO.
Tu tarea es responder a la pregunta del usuario utilizando ÚNICAMENTE la información oficial extraída del motor determinista.
Si la información proporcionada no contiene la respuesta, di: "No tengo datos suficientes en mi base de datos para responder".
NO ALUCINES NI INVENTES INFORMACIÓN.

--- INFORMACIÓN OFICIAL DEL ÍNDICE LOCAL ---
{contexto}
-------------------------------------------"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {nvidia_key}",
                    "Accept": "application/json",
                },
                json={
                    "model": "minimaxai/minimax-m3",
                    "messages": [
                        {"role": "system", "content": prompt_sistema},
                        {"role": "user",   "content": data.pregunta}
                    ],
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "max_tokens": 512,
                    "stream": False
                }
            )
        if res.status_code == 200:
            respuesta_ia = res.json()["choices"][0]["message"]["content"]
        elif res.status_code == 429:
            raise HTTPException(429, "Límite de solicitudes NVIDIA alcanzado. Intenta en unos segundos.")
        else:
            raise HTTPException(502, f"Error NVIDIA API: HTTP {res.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(504, "La IA tardó demasiado en responder. Intenta nuevamente.")

    return {
        "pregunta": data.pregunta,
        "contexto_local": {
            "encontrado": contexto_encontrado,
            "documentos": len(resultados),
            "fragmentos": [{"nombre": d["nombre"], "fragmento": d["fragmento"]} for d in resultados]
        },
        "respuesta_ia": respuesta_ia,
        "modelo": "minimaxai/minimax-m3"
    }
