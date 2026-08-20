import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from export_informe_fuentes import cargar_informe
from export_informe_osint import (
    Documento,
    InformeData,
    build_informe_desde_entries,
    datos_ejemplo,
    generar_informe_osint_bytes,
)
from export_transcripcion_ia import ChatData, MensajeChat, generar_transcripcion_bytes


def test_export_informe_osint_dataclasses():
    doc = Documento(
        doc_num="1",
        titulo="Test Doc",
        fuente="rss",
        score_sentimiento=0.25,
        url="https://example.org",
        analisis="Test analysis",
        contenido="Test content",
    )
    d = doc.to_dict()
    doc2 = Documento.from_dict(d)
    assert doc2.doc_num == "1"
    assert doc2.titulo == "Test Doc"
    assert doc2.score_sentimiento == 0.25

    info = datos_ejemplo()
    info_dict = info.to_dict()
    info2 = InformeData.from_dict(info_dict)
    assert info2.codigo == info.codigo
    assert len(info2.documentos) == len(info.documentos)


def test_generar_informe_osint_bytes():
    info = datos_ejemplo()
    bytes_data = generar_informe_osint_bytes(info)
    assert isinstance(bytes_data, bytes)
    assert len(bytes_data) > 1000
    assert bytes_data.startswith(b"PK")


def test_build_informe_desde_entries():
    sample_entries = [
        {
            "id": "entry-1",
            "title": "Noticia de Prueba 1",
            "source": "rss_test",
            "sentiment_score": 0.5,
            "link": "https://test.com/1",
            "summary": "Resumen de prueba 1",
            "bot_probability": 0.8,
        },
        {
            "id": "entry-2",
            "title": "Noticia de Prueba 2",
            "source": "vk_test",
            "sentiment_score": -0.2,
            "link": "https://test.com/2",
            "summary": "Resumen de prueba 2",
            "bot_probability": 0.1,
        },
    ]
    info = build_informe_desde_entries(sample_entries, max_docs=10)
    assert len(info.documentos) == 2
    assert info.documentos[0].titulo == "Noticia de Prueba 1"
    assert info.doc_con_bot == 1
    assert info.nivel_alerta == "POSIBLE CAMPAÑA COORDINADA"


def test_export_transcripcion_ia_bytes():
    chat_data = ChatData(
        nombre_usuario="Analista COBALTO",
        modelo="llama3.2",
        temperatura=0.7,
        fecha="12/08/2026 14:00",
        mensajes=[
            MensajeChat(role="user", content="¿Cuál es la amenaza actual?"),
            MensajeChat(role="assistant", content="Se detecta actividad anómala en fuentes sociales."),
        ],
    )
    bytes_data = generar_transcripcion_bytes(chat_data)
    assert isinstance(bytes_data, bytes)
    assert len(bytes_data) > 1000
    assert bytes_data.startswith(b"PK")


def test_export_informe_fuentes_failover():
    res = cargar_informe(entries=[{"title": "Test Entry", "source": "test"}])
    assert res.origen == "contexto"
    assert len(res.datos.documentos) > 0

    res_fallback = cargar_informe()
    assert res_fallback.origen in ("sqlite", "json", "ejemplo")
    assert len(res_fallback.datos.documentos) > 0


async def test_ejecutar_investigacion_local_sin_ia():
    from intel_reports import ejecutar_investigacion_local, generar_docx_informe, generar_pdf_informe, obtener_historial_informes

    sample_entries = [
        {
            "id": "entry-1",
            "title": "Protesta y apagón reportado en Caracas V-12345678",
            "source": "rss_test",
            "sentiment_score": -0.6,
            "link": "https://test.com/1",
            "summary": "Corte de servicio eléctrico y movilización reportada en Caracas. Cédula V-12345678 registrada.",
        }
    ]

    report = await ejecutar_investigacion_local(
        query="apagón y protesta",
        preset="general",
        include_rag=True,
        use_ai=False,
        entries_pool=sample_entries
    )

    assert report.tema_investigacion == "apagón y protesta"
    assert "Motor Fáctico" in report.autor
    assert report.total_analizados == 1
    assert "ALERTA" in report.nivel_alerta
    assert "REGISTRO DE ENTIDADES" in report.analisis_completo
    assert "GEOLOCALIZACIÓN" in report.analisis_completo
    
    hist = obtener_historial_informes()
    assert len(hist) > 0
    assert hist[0]["codigo"] == report.codigo

    docx_bytes = generar_docx_informe(report)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 1000

    pdf_bytes = generar_pdf_informe(report)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500

