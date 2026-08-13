"""Tests para el modulo intel_reports.py y generacion de informes DOCX/PDF."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from intel_reports import (
    DocumentoIntel,
    InformeIntelData,
    generar_docx_informe,
    generar_pdf_informe,
)


def test_informe_intel_dataclasses():
    doc = DocumentoIntel(
        doc_num="1",
        titulo="Noticia Test",
        fuente="RSS Test",
        score_sentimiento=-0.5,
        url="http://test.com",
        contenido="Contenido de prueba OSINT",
    )
    assert doc.doc_num == "1"
    assert doc.score_sentimiento == -0.5

    data = InformeIntelData(
        codigo="TEST-001",
        fecha_creacion="12/08/2026",
        autor="Analista Test",
        institucion="C4I",
        fuente_datos="Ollama",
        fecha_analisis="12/08/2026",
        tema_investigacion="Apagones y Redes",
        resumen_ejecutivo="Resumen de prueba",
        analisis_completo="Analisis completo de prueba",
        documentos=[doc],
        total_analizados=1,
    )
    d_dict = data.to_dict()
    assert d_dict["codigo"] == "TEST-001"
    assert len(d_dict["documentos"]) == 1


def test_generar_docx_bytes():
    doc = DocumentoIntel(
        doc_num="1",
        titulo="Test Doc",
        fuente="Test Source",
        contenido="Test content body",
    )
    data = InformeIntelData(
        codigo="TEST-002",
        fecha_creacion="12/08/2026",
        autor="Analista Test",
        institucion="C4I",
        fuente_datos="Ollama Local",
        fecha_analisis="12/08/2026",
        tema_investigacion="Investigacion Maritima",
        analisis_completo="Analisis tactico de prueba",
        documentos=[doc],
        total_analizados=1,
    )
    docx_bytes = generar_docx_informe(data)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 500


def test_generar_pdf_bytes():
    doc = DocumentoIntel(
        doc_num="1",
        titulo="Test Doc PDF",
        fuente="Test Source PDF",
        contenido="Test content body PDF",
    )
    data = InformeIntelData(
        codigo="TEST-003",
        fecha_creacion="12/08/2026",
        autor="Analista Test",
        institucion="C4I",
        fuente_datos="Ollama Local",
        fecha_analisis="12/08/2026",
        tema_investigacion="Seguridad Nacional",
        analisis_completo="Analisis tactico de prueba PDF",
        documentos=[doc],
        total_analizados=1,
    )
    pdf_bytes = generar_pdf_informe(data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
