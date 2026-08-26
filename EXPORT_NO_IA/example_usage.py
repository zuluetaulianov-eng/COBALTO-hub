"""
EJEMPLO DE USO - GENERACIÓN DE INFORMES DETERMINISTAS (SIN IA)
==============================================================
Script independiente de demostración para generar reportes en JSON,
Word (.docx), PDF (.pdf) e Informes de Inteligencia OSINT sin ninguna API de IA.
"""

import json

from report_engine_no_ia import procesar_entrada_determinista, procesar_lote_determinista

from export_informe_osint import DocumentoNoticioso, InformeOSINTData, generar_informe_osint_bytes
from export_sitrep_docx import generate_sitrep_docx_bytes
from export_sitrep_pdf import generate_sitrep_pdf_bytes


def main():
    print("=== 1. Análisis Determinista de una Noticia / Evento ===")
    resultado = procesar_entrada_determinista(
        titulo="Reportan falla en el suministro eléctrico en estación de bombeo",
        contenido="Unidades de respuesta técnica atienden avería en el sistema principal. Se descartan sabotajes cibernéticos iniciales.",
        fuente="Prensa Regional",
    )
    print("Resultado JSON Determinista:")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print("\n")

    print("=== 2. Procesamiento de Lote Determinista ===")
    noticias_prueba = [
        {"titulo": "Alerta por aumento de oleaje en zona costera", "contenido": "Autoridades emiten aviso de precaución a embarcaciones menores.", "fuente": "Protección Civil"},
        {"titulo": "Ciberataque tipo ransomware afecta servidor administrativo", "contenido": "Sistemas aislados preventivamente. Equipo de seguridad investiga el vector de ataque.", "fuente": "Seguridad Digital"},
    ]
    lote_procesado = procesar_lote_determinista(noticias_prueba)
    print(f"Lote procesado exitosamente ({len(lote_procesado)} elementos ordenados por nivel de riesgo).")
    print(f"Noticia más crítica: {lote_procesado[0]['titulo']} -> {lote_procesado[0]['analisis_determinista']['nivel_amenaza']}")
    print("\n")

    print("=== 3. Generación de Archivo DOCX (Microsoft Word) ===")
    docx_bytes = generate_sitrep_docx_bytes({"entries": noticias_prueba, "alerts": [{"tipo": "SISTEMA", "mensaje": "Alerta preventiva"}]})
    with open("EXPORT_NO_IA/SITREP_DETERMINISTA.docx", "wb") as f:
        f.write(docx_bytes)
    print("Archivo 'EXPORT_NO_IA/SITREP_DETERMINISTA.docx' generado con éxito.\n")

    print("=== 4. Generación de Archivo PDF ===")
    try:
        pdf_bytes = generate_sitrep_pdf_bytes({"entries": noticias_prueba, "alerts": []})
        with open("EXPORT_NO_IA/SITREP_DETERMINISTA.pdf", "wb") as f:
            f.write(pdf_bytes)
        print("Archivo 'EXPORT_NO_IA/SITREP_DETERMINISTA.pdf' generado con éxito.\n")
    except Exception as e:
        print(f"Generación de PDF omitida: {e}\n")

    print("=== 5. Generación de Informe OSINT Ejecutivo (DOCX) ===")
    datos_osint = InformeOSINTData(
        codigo="INT-NOIA-2026-001",
        fecha_creacion="25 de agosto de 2026",
        autor="Motor Determinista No-IA",
        institucion="C4I OSINT",
        fuente_datos="COBALTO HUB Determinista",
        fecha_analisis="25/08/2026",
        documentos=[
            DocumentoNoticioso(
                doc_num="1",
                titulo=noticias_prueba[1]["titulo"],
                fuente=noticias_prueba[1]["fuente"],
                score_sentimiento=-0.85,
                analisis="Amenaza cibernética confirmada por reglas sintácticas.",
                contenido=noticias_prueba[1]["contenido"],
            )
        ],
    )
    osint_bytes = generar_informe_osint_bytes(datos_osint)
    with open("EXPORT_NO_IA/INFORME_OSINT_EJECUTIVO.docx", "wb") as f:
        f.write(osint_bytes)
    print("Archivo 'EXPORT_NO_IA/INFORME_OSINT_EJECUTIVO.docx' generado con éxito.")


if __name__ == "__main__":
    main()
