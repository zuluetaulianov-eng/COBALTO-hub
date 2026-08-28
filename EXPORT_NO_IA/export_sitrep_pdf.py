"""
EXPORT SITREP PDF (Generador Determinista de Informes PDF)
=========================================================
Construye informes de situación (SITREP) en formato PDF utilizando FPDF2
con banners vectoriales, código de colores por criticidad, tablas y pie de página.
SIN DEPENDENCIAS DE IA.
"""

import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger("SitrepPDFNoIA")

try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

COLORS = {
    "critical": (220, 38, 38),
    "high": (234, 88, 12),
    "medium": (202, 138, 4),
    "stable": (22, 163, 74),
    "dark": (15, 23, 42),
    "cyan": (2, 132, 199),
    "muted": (100, 116, 139),
    "light_bg": (248, 250, 252),
}


class SitrepPDF(FPDF if HAS_FPDF else object):
    def header(self):
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*COLORS["muted"])
        self.cell(0, 5, "SITREP COBALTO - GENERACIÓN DETERMINISTA SIN IA", align="L")
        self.ln(3)
        self.set_draw_color(*COLORS["dark"])
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*COLORS["muted"])
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}} | DOCUMENTO OFICIAL NO CLASIFICADO", align="C")


def generate_sitrep_pdf_bytes(contexto: Dict[str, Any]) -> bytes:
    """Genera un informe SITREP en PDF determinísticamente como bytes."""
    if not HAS_FPDF:
        raise RuntimeError("fpdf2 no está instalado. Ejecuta: pip install fpdf2")

    entries = contexto.get("entries", contexto.get("all_entries", []))
    alerts = contexto.get("alerts", [])

    pdf = SitrepPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Banner Superior
    pdf.set_fill_color(*COLORS["dark"])
    pdf.rect(10, 10, 190, 20, style="F")
    pdf.set_xy(15, 12)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 6, "SITREP DE INTELIGENCIA (NO-IA)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 229, 255)
    pdf.cell(0, 4, f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} | Entradas: {len(entries)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(8)

    # Tabla Metadatos
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*COLORS["muted"])
    pdf.cell(45, 6, "Estado Motor:", border=1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*COLORS["stable"])
    pdf.cell(50, 6, "DETERMINISTA (100% OK)", border=1)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*COLORS["muted"])
    pdf.cell(45, 6, "Alertas Registradas:", border=1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*COLORS["critical"] if alerts else COLORS["stable"])
    pdf.cell(50, 6, str(len(alerts)), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    # Tabla de Noticias
    if entries:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*COLORS["cyan"])
        pdf.cell(0, 6, "Registro de Eventos y Amenaza Estimada", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

        # Encabezado Tabla
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(*COLORS["dark"])
        pdf.set_text_color(255, 255, 255)
        pdf.cell(10, 6, "#", border=1, fill=True, align="C")
        pdf.cell(110, 6, "Evento / Título", border=1, fill=True, align="L")
        pdf.cell(40, 6, "Fuente", border=1, fill=True, align="C")
        pdf.cell(30, 6, "Amenaza", border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(0, 0, 0)

        for idx, item in enumerate(entries[:30]):
            titulo = str(item.get("titulo", item.get("title", "")))[:55]
            fuente = str(item.get("fuente", item.get("source", "OSINT")))[:20]
            analisis = item.get("analisis_determinista", {})
            amenaza = analisis.get("nivel_amenaza", "MEDIA")

            pdf.cell(10, 6, str(idx + 1), border=1, align="C")
            pdf.cell(110, 6, titulo, border=1, align="L")
            pdf.cell(40, 6, fuente, border=1, align="C")
            pdf.cell(30, 6, amenaza, border=1, align="C")
            pdf.ln()

    return pdf.output()
