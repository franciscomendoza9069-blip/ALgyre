"""Render immutable ledger snapshots into internal PDF reports."""

import io
from decimal import Decimal
from xml.sax.saxutils import escape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from .environment import CAT


def pdf_report(s, stamp):
    out = io.BytesIO()
    styles = getSampleStyleSheet()
    styles["BodyText"].leading = 15
    flow = []

    def p(t, style="BodyText"):
        flow.append(Paragraph(escape(str(t)), styles[style]))
        flow.append(Spacer(1, 3 * mm))

    p("ALgyre | Informe de emisiones calculadas", "Title")
    p(f"{s['company']['name']} · {s['year']}", "Heading1")
    if s["demo"]:
        p("EJEMPLO FICTICIO. No utilizar para comunicar emisiones reales.", "Heading2")
    p(
        "Informe interno parcial. No constituye una certificación ni una verificación externa."
    )
    p("Creado en UTC: " + stamp)
    p("Perímetro declarado: " + (s["company"]["boundary"] or "Sin definir"))
    p(
        "Exclusiones y supuestos: "
        + (
            s["company"]["exclusions"]
            or "Sin declarar; revisar otras fuentes de emisión."
        )
    )
    su = s["summary"]
    p(f"Total de fuentes calculadas: {Decimal(su['total']):,.3f} kg CO2e", "Heading2")
    p(
        f"Alcance 1 incluido: {Decimal(su['scope1']):,.3f} kg CO2e. Alcance 2 incluido: {Decimal(su['scope2']):,.3f} kg CO2e."
    )
    if "scope3" in su:
        p(
            f"Alcance 3 incluido: {Decimal(su['scope3']):,.3f} kg CO2e. Solo categorías registradas; no equivale a un inventario completo."
        )
    p(
        f"Pendientes de cálculo: {su['pending']}. Meses-categoría completos: {su['covered']} de {su['expected']}. La cobertura temporal se refiere solo a suministros continuos declarados y exige cubrir todos los días del mes."
    )
    p(
        "Método: cantidad normalizada × factor documentado. 1 MWh = 1000 kWh; 1 t = 1000 kg. Factores seleccionados por actividad, país, año y unidad; no se convierten m3 de gas a kWh sin equivalencia. La distribución mensual se estima por días de cada periodo. Las instantáneas conservan cantidades y factores usados; cambios posteriores requieren un informe nuevo."
    )
    if "catalog" in s:
        p(
            "Electricidad: método territorial. Refrigerantes: masa emitida × potencial de calentamiento global documentado. Las actividades indirectas requieren factores específicos y revisión de límites para evitar duplicidades. No se descuentan compensaciones. Agua expresa emisiones del suministro, no huella hídrica."
        )
    p("Detalle y trazabilidad", "Heading2")
    for r in s["records"]:
        p(
            f"{r['facility_name']} / {CAT[r['category']]} / {r['start']} a {r['end']}",
            "Heading3",
        )
        p(
            f"{r['quantity']} {r['unit']} | Referencia: {r['reference'] or 'sin referencia'} | Revisión: {r['revision']}"
        )
        if "scope" in r:
            p(
                f"Alcance: {r['scope']}"
                + (
                    f" · Categoría de alcance 3: {r['scope3_category']}"
                    if r.get("scope3_category")
                    else ""
                )
            )
        f = r["factor"]
        if r["kg_co2e"] is not None:
            p(
                f"Resultado: {r['kg_co2e']} kg CO2e. Factor: {f['value']} kg CO2e/{f['unit']}; {f['name']}; versión {f['version']}; {f['country']}, {f['year']}. Fuente: {f['source']}"
            )
        else:
            p("Pendiente: " + r["pending_reason"])
        p(
            "Documento: "
            + (r["document_name"] or "Entrada manual, sin archivo adjunto")
            + " | ID de consumo: "
            + r["id"]
        )
        if r["note"]:
            p("Notas: " + r["note"])
    p("Fuentes declaradas con días sin datos", "Heading2")
    if not su["gaps"]:
        p(
            "Sin huecos detectados en las fuentes declaradas, o sin fuentes configuradas. Comprobar el perímetro."
        )
    for g in su["gaps"]:
        p(f"{g['facility']} / {g['category']} / mes {g['month']}")

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, 12 * mm, f"ALgyre | Uso interno | Página {doc.page}")

    SimpleDocTemplate(
        out,
        pagesize=(210 * mm, 297 * mm),
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
    ).build(flow, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
