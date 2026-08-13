import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from fpdf import FPDF

    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False
    logger.warning("fpdf2 no instalado. pip install fpdf2")


class SitrepPDFError(Exception):
    pass


def _sanitize(val):
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


_COLORS = {
    "critical": (229, 62, 62),
    "high": (221, 107, 32),
    "medium": (214, 158, 46),
    "stable": (56, 161, 105),
    "dark": (26, 26, 46),
    "cyan": (0, 229, 255),
    "muted": (113, 128, 150),
    "light_bg": (247, 250, 252),
}


class SitrepPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*_COLORS["muted"])
        self.cell(0, 5, "SITREP COBALTO - Sistema de Inteligencia OSINT C4I", align="L")
        self.ln(3)
        self.set_draw_color(*_COLORS["dark"])
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*_COLORS["muted"])
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}} | CLASIFICACION: NO CLASIFICADO - USO INTERNO", align="C")

    def section_title(self, title, color=None):
        if color is None:
            color = _COLORS["critical"]
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*_COLORS["dark"])
        self.set_draw_color(*color)
        x = self.get_x()
        self.set_fill_color(240, 242, 247)
        self.cell(0, 8, f"  {title}", fill=True, ln=True)
        self.line(x, self.get_y(), x + 190, self.get_y())
        self.ln(3)

    def meta_row(self, label, value, value_color=None):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*_COLORS["muted"])
        self.cell(45, 6, label, border=1)
        self.set_font("Helvetica", "", 9)
        if value_color:
            self.set_text_color(*value_color)
        else:
            self.set_text_color(0, 0, 0)
        self.cell(55, 6, str(value), border=1)
        return self

    def data_table(self, headers, rows, col_widths=None):
        if not rows:
            return
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)
        self.set_font("Helvetica", "B", 7)
        self.set_fill_color(*_COLORS["dark"])
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 6, h, border=1, fill=True, align="C")
        self.ln()
        self.set_font("Helvetica", "", 7)
        fill = False
        for row in rows:
            if fill:
                self.set_fill_color(*_COLORS["light_bg"])
            else:
                self.set_fill_color(255, 255, 255)
            max_h = 6
            for i, cell in enumerate(row):
                self.set_text_color(0, 0, 0)
                if isinstance(cell, tuple):
                    self.set_text_color(*cell[1])
                    cell = cell[0]
                self.cell(col_widths[i], 6, str(cell)[:60], border=1, fill=fill, align="C" if i > 0 else "L")
            self.ln()
            fill = not fill
        self.ln(3)

    def body_text(self, text, size=9):
        self.set_font("Helvetica", "", size)
        self.set_text_color(45, 55, 72)
        self.multi_cell(0, 5, str(text))
        self.ln(2)

    def alert_box(self, title, text, color=None):
        if color is None:
            color = _COLORS["critical"]
        self.set_fill_color(*color)
        x = self.get_x()
        y = self.get_y()
        self.rect(x, y, 3, 20, style="F")
        self.set_x(x + 5)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*color)
        self.cell(0, 5, title, ln=True)
        self.set_x(x + 5)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(45, 55, 72)
        self.multi_cell(175, 4, text)
        self.ln(4)


def generate_sitrep_pdf(ctx: dict) -> bytes:
    if not HAS_FPDF:
        raise SitrepPDFError("fpdf2 no esta instalado. pip install fpdf2")

    entries = ctx.get("all_entries", [])
    if not isinstance(entries, list):
        entries = []
    alerts = ctx.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = []
    outages_raw = ctx.get("events_data", {}).get("network_outages", [])
    if not isinstance(outages_raw, list):
        outages_raw = ctx.get("network_outages", [])
    if not isinstance(outages_raw, list):
        outages_raw = []
    briefing = ctx.get("global_briefing", {})

    from ai_core import is_ai_available as _check_ai
    from humanization import STRESS_MONITOR

    total_alerts = len(alerts)
    total_entries = len(entries)
    cb_count = ctx.get("cb_count", 0)
    total_sources = ctx.get("total_sources", 0)
    cycle_id = str(ctx.get("cycle_id", "N/A"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    groq_avail = "DISPONIBLE" if _check_ai() else "NO DISPONIBLE"
    stress_lvl = str(round(STRESS_MONITOR.scaling_factor, 1))

    if total_alerts > 20:
        criticidad = "CRITICA"
        alert_color = _COLORS["critical"]
    elif total_alerts > 5:
        criticidad = "ALTA"
        alert_color = _COLORS["high"]
    elif total_alerts > 0:
        criticidad = "MEDIA"
        alert_color = _COLORS["medium"]
    else:
        criticidad = "ESTABLE"
        alert_color = _COLORS["stable"]

    pdf = SitrepPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── Banner ──
    pdf.set_fill_color(*_COLORS["dark"])
    pdf.rect(10, 10, 190, 22, style="F")
    pdf.set_xy(15, 12)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, "SITREP COBALTO", ln=True)
    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_COLORS["cyan"])
    pdf.cell(0, 5, "Sistema de Inteligencia OSINT C4I - Reporte de Situacion", ln=True)
    pdf.set_x(15)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(*alert_color)
    pdf.cell(30, 5, f"CRITICIDAD: {criticidad}", fill=True, ln=True)
    pdf.ln(8)

    # ── Meta table ──
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_COLORS["muted"])
    pdf.cell(35, 5, "Version:", border=1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(45, 5, "1.0", border=1)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_COLORS["muted"])
    pdf.cell(35, 5, "Generado:", border=1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(75, 5, now, border=1, ln=True)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_COLORS["muted"])
    pdf.cell(35, 5, "Ciclo ID:", border=1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(45, 5, cycle_id, border=1)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_COLORS["muted"])
    pdf.cell(35, 5, "Groq IA:", border=1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_COLORS["stable"])
    pdf.cell(75, 5, groq_avail, border=1, ln=True)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_COLORS["muted"])
    pdf.cell(35, 5, "Total Entradas:", border=1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(45, 5, str(total_entries), border=1)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_COLORS["muted"])
    pdf.cell(35, 5, "Total Alertas:", border=1)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*alert_color)
    pdf.cell(75, 5, str(total_alerts), border=1, ln=True)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_COLORS["muted"])
    pdf.cell(35, 5, "CB Abiertos:", border=1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(45, 5, str(cb_count), border=1)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_COLORS["muted"])
    pdf.cell(35, 5, "Stress Level:", border=1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(75, 5, stress_lvl, border=1, ln=True)
    pdf.ln(5)

    # ── Alertas ──
    if alerts:
        pdf.section_title("2. Alertas Activas", alert_color)
        alert_rows = []
        for a in alerts[:30]:
            if not isinstance(a, dict):
                continue
            sev = str(a.get("severity", a.get("severidad", "info"))).lower()
            sev_color = _COLORS["critical"] if "alta" in sev or "crit" in sev else _COLORS["high"] if "media" in sev or "warning" in sev else _COLORS["stable"]
            alert_rows.append([
                str(a.get("type", a.get("tipo", "")))[:20],
                (sev.upper(), sev_color),
                str(a.get("source", a.get("fuente", "")))[:20],
                str(a.get("timestamp", a.get("time", "")))[:15],
            ])
        pdf.data_table(["Tipo", "Severidad", "Fuente", "Timestamp"], alert_rows, [35, 30, 45, 40])

    # ── Outages ──
    if outages_raw:
        pdf.section_title("3. Apagones de Red", _COLORS["high"])
        outage_rows = []
        for o in outages_raw[:20]:
            if not isinstance(o, dict):
                continue
            drop = float(str(o.get("drop_percent", o.get("drop", "0"))).replace("%", ""))
            drop_color = _COLORS["critical"] if drop > 50 else _COLORS["high"]
            outage_rows.append([
                str(o.get("asn", o.get("asn_number", "")))[:20],
                str(o.get("country", o.get("country_code", ""))),
                (f"{drop}%", drop_color),
            ])
        pdf.data_table(["ASN", "Pais", "Caida"], outage_rows, [50, 40, 40])

    # ── Entradas ──
    if entries:
        pdf.section_title("4. Entradas OSINT Recientes", _COLORS["dark"])
        entry_rows = []
        for i, e in enumerate(entries[:40]):
            if not isinstance(e, dict):
                continue
            entry_rows.append([
                str(i + 1),
                str(e.get("title", e.get("titulo", "")))[:40],
                str(e.get("source", e.get("fuente", "")))[:15],
                str(e.get("published", e.get("fecha", "")))[:12],
            ])
        pdf.data_table(["#", "Titulo", "Fuente", "Fecha"], entry_rows, [10, 80, 40, 30])

    # ── Briefing ──
    if briefing:
        pdf.section_title("5. Briefing de Inteligencia (IA)", _COLORS["stable"])
        if isinstance(briefing, dict):
            summary = str(briefing.get("summary", briefing.get("resumen", str(briefing))))
        else:
            summary = str(briefing)
        pdf.body_text(summary)

    # ── Output ──
    return pdf.output()
