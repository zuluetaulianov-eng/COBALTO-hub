import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

logger = logging.getLogger("cobalto.reportes")
from backend.models.reporte import AnalisisIA, GenerarWordRequest, ReporteRequest
from backend.services.docx_service import DocxGenerationError, generar_documento_word
from backend.services.groq_service import GroqAnalysisError, obtener_analisis_ia

router = APIRouter(prefix="/api/reportes", tags=["Reportes"])


@router.post("/analizar-ia", response_model=list[AnalisisIA])
async def analizar_ia(payload: ReporteRequest, request: Request):
    ip_client = request.client.host if request.client else "unknown"
    logger.info(f"Iniciando análisis IA | IP: {ip_client} | Novedades: {len(payload.novedades)}")
    if not payload.novedades:
        raise HTTPException(status_code=422, detail="Debe incluir al menos una novedad.")

    for i, novedad in enumerate(payload.novedades):
        if not novedad.texto_situacion.strip():
            raise HTTPException(
                status_code=422,
                detail=f"La novedad #{i + 1} no tiene texto de situación.",
            )

    try:
        analisis_list = []
        for novedad in payload.novedades:
            descripciones = [img.descripcion for img in novedad.imagenes if img.descripcion]
            analisis_dict = await obtener_analisis_ia(
                novedad.fecha_situacion,
                novedad.texto_situacion,
                descripciones
            )
            # Normalizar en caso de faltantes
            actores = analisis_dict.get("actores", [])
            if isinstance(actores, str): actores = [actores]
            analisis_list.append(AnalisisIA(
                actores=actores,
                amenaza=str(analisis_dict.get("amenaza", "Desconocida")),
                analisis=str(analisis_dict.get("analisis", ""))
            ))
        return analisis_list
    except GroqAnalysisError as e:
        logger.error(f"Error en IA de Groq para IP {ip_client}: {e}")
        raise HTTPException(status_code=504, detail=str(e))


@router.post("/generar-word")
async def generar_reporte_word(payload: GenerarWordRequest, request: Request):
    ip_client = request.client.host if request.client else "unknown"
    logger.info(f"Iniciando generacion de reporte final | IP: {ip_client} | Novedades: {len(payload.novedades)}")

    if not payload.novedades:
        raise HTTPException(status_code=422, detail="Debe incluir al menos una novedad.")

    if len(payload.novedades) != len(payload.analisis_por_novedad):
        raise HTTPException(status_code=422, detail="La cantidad de análisis debe coincidir con la cantidad de novedades.")

    analisis_dicts = [a.model_dump() for a in payload.analisis_por_novedad]

    try:
        doc_bytes = await generar_documento_word(payload, analisis_dicts)
    except DocxGenerationError as e:
        logger.error(f"Error al generar Docx para IP {ip_client}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    logger.info(f"Reporte generado exitosamente para IP {ip_client}. Tamaño: {len(doc_bytes)} bytes")
    return Response(
        content=doc_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": "attachment; filename=Reporte_Patrullaje_Cobalto.docx"
        },
    )
