"""Bounded PDF text extraction; suggestions always require human review."""

import io
import re
from datetime import date
from pypdf import PdfReader
from .common import number


def extract_pdf(content):
    try:
        pdf = PdfReader(io.BytesIO(content))
        if pdf.is_encrypted:
            raise ValueError("El PDF está protegido. Guarda una copia sin contraseña.")
        if len(pdf.pages) > 60:
            raise ValueError("Usa un PDF de hasta 60 páginas.")
        body = "\n".join(p.extract_text() or "" for p in pdf.pages)[:120000]
    except ValueError:
        raise
    except Exception:
        raise ValueError("No se pudo leer este PDF. Comprueba que no esté dañado.")
    suggestions = {}
    quantities = re.findall(r"([\d][\d., ]*)\s*(kWh|MWh|litros|m3|m³)\b", body, re.I)
    if len(quantities) == 1:
        raw, unit = quantities[0]
        try:
            suggestions["quantity"] = str(number(raw))
            suggestions["unit"] = {
                "kwh": "kWh",
                "mwh": "MWh",
                "litros": "L",
                "m³": "m3",
            }.get(unit.lower(), unit)
        except ValueError:
            pass
    dates = re.findall(r"\b(\d{2})[/-](\d{2})[/-](20\d{2})\b", body)
    valid = []
    for day, month, year in dates:
        try:
            valid.append(date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            pass
    if len(valid) == 2:
        suggestions.update(start=min(valid), end=max(valid))
    suggestions["message"] = (
        "Texto extraído. Comprueba todos los campos con la factura."
        if body.strip()
        else "PDF sin texto seleccionable. Introduce los consumos manualmente consultando el archivo."
    )
    return body, suggestions
