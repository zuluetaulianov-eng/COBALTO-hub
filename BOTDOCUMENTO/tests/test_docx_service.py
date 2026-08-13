import httpx
import pytest
from backend.models.reporte import ImagenAnexo, NovedadPatrullaje, ReporteRequest
from backend.services.docx_service import generar_documento_word, set_http_client


@pytest.fixture(autouse=True)
def _setup_http_client():
    client = httpx.AsyncClient()
    set_http_client(client)
    yield
    import asyncio
    try:
        asyncio.get_event_loop().run_until_complete(client.aclose())
    except RuntimeError:
        pass


@pytest.mark.asyncio
async def test_generar_docx_basico():
    payload = ReporteRequest(
        novedades=[
            NovedadPatrullaje(
                fecha_situacion="17JUN2026",
                portal_web_url="https://example.com",
                texto_situacion="Texto de prueba para la novedad.",
                imagenes=[],
            )
        ]
    )
    analisis = [{"actores": ["Test Actor"], "amenaza": "Baja", "analisis": "Análisis simulado de IA para la prueba."}]
    doc_bytes = await generar_documento_word(payload, analisis)
    assert isinstance(doc_bytes, bytes)
    assert len(doc_bytes) > 0
    assert doc_bytes[:4] == b'PK\x03\x04'


@pytest.mark.asyncio
async def test_generar_docx_multiples_novedades():
    payload = ReporteRequest(
        novedades=[
            NovedadPatrullaje(
                fecha_situacion="17JUN2026",
                portal_web_url="https://example.com/1",
                texto_situacion="Primera novedad de prueba.",
                imagenes=[],
            ),
            NovedadPatrullaje(
                fecha_situacion="18JUN2026",
                portal_web_url="https://example.com/2",
                texto_situacion="Segunda novedad de prueba.",
                imagenes=[],
            ),
        ]
    )
    analisis = [
        {"actores": ["Actor 1"], "amenaza": "Media", "analisis": "Análisis 1"},
        {"actores": ["Actor 2"], "amenaza": "Alta", "analisis": "Análisis 2"}
    ]
    doc_bytes = await generar_documento_word(payload, analisis)
    assert len(doc_bytes) > 0


@pytest.mark.asyncio
async def test_generar_docx_con_imagen_sin_url():
    payload = ReporteRequest(
        novedades=[
            NovedadPatrullaje(
                fecha_situacion="17JUN2026",
                portal_web_url="https://example.com",
                texto_situacion="Test con imagen vacía.",
                imagenes=[ImagenAnexo(url=None, descripcion="")],
            )
        ]
    )
    analisis = [{"actores": ["Test Actor"], "amenaza": "Baja", "analisis": "Análisis de prueba."}]
    doc_bytes = await generar_documento_word(payload, analisis)
    assert isinstance(doc_bytes, bytes)
    assert len(doc_bytes) > 0


@pytest.mark.asyncio
async def test_generar_docx_vacio():
    payload = ReporteRequest(novedades=[])
    doc_bytes = await generar_documento_word(payload, [])
    assert isinstance(doc_bytes, bytes)
    assert len(doc_bytes) > 0
