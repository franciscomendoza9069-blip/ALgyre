"""Local spreadsheet ingestion. Own mapping rules; no remote services."""

import base64
import csv
import io
import re
import unicodedata
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook, load_workbook
from algyre_core.environment import ACTIVITIES, UNIT_LABELS

FIELDS = {
    "facility": "Instalación",
    "category": "Categoría",
    "quantity": "Cantidad",
    "unit": "Unidad",
    "start": "Inicio",
    "end": "Fin",
    "supplier": "Proveedor",
    "reference": "Referencia",
    "note": "Notas",
    "document": "Documento PDF",
}
ALIASES = {
    "facility": ["instalacion", "facility", "facility name", "instalación"],
    "category": [
        "categoria",
        "categoría",
        "category",
        "stationary fuel",
        "combustible",
    ],
    "quantity": ["cantidad", "quantity", "consumo"],
    "unit": ["unidad", "unit"],
    "start": ["inicio", "start date", "fecha inicio"],
    "end": ["fin", "end date", "fecha fin"],
    "supplier": ["proveedor", "supplier"],
    "reference": ["referencia", "invoice id", "factura"],
    "note": ["notas", "notes", "note"],
    "document": ["documento", "documento pdf", "document"],
}


def normalized(value):
    value = re.sub(r"\s*\((?:optional|opcional)\)\s*", "", str(value), flags=re.I)
    value = "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )
    return " ".join(value.strip().lower().split())


def cell_text(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    result = str(value).strip()
    if len(result) > 2000:
        raise ValueError("Una celda supera 2000 caracteres.")
    return result


def read_upload(name, encoded, sheet=None):
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise ValueError("No se pudo leer el archivo.")
    if not content or len(content) > 5_000_000:
        raise ValueError("Selecciona un archivo de hasta 5 MB.")
    if name.lower().endswith(".csv"):
        if len(content) > 2_000_000:
            raise ValueError("El CSV supera 2 MB.")
        try:
            body = content.decode("utf-8-sig")
            dialect = csv.Sniffer().sniff(body[:4096], delimiters=";,\t")
            grid = list(csv.reader(io.StringIO(body), dialect))
        except (UnicodeError, csv.Error):
            raise ValueError(
                "Utiliza CSV UTF-8 separado por coma, punto y coma o tabulador."
            )
        sheets, selected = ["CSV"], "CSV"
    elif name.lower().endswith(".xlsx"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if (
                    len(archive.infolist()) > 2000
                    or sum(i.file_size for i in archive.infolist()) > 20_000_000
                ):
                    raise ValueError("El Excel descomprimido es demasiado grande.")
                if any(
                    "vbaproject" in n.lower() or "externallinks/" in n.lower()
                    for n in archive.namelist()
                ):
                    raise ValueError("Utiliza un Excel sin macros ni enlaces externos.")
            book = load_workbook(
                io.BytesIO(content), read_only=True, data_only=False, keep_links=False
            )
            try:
                sheets = book.sheetnames
                selected = sheet or sheets[0]
                if selected not in sheets:
                    raise ValueError("La hoja seleccionada no existe.")
                ws = book[selected]
                if ws.max_column and ws.max_column > 50:
                    raise ValueError("Admitimos hasta 50 columnas por hoja.")
                # Read bounded cells, even when the workbook declares misleading dimensions.
                ws.reset_dimensions()
                grid = []
                for row in ws.iter_rows(max_col=51, values_only=True):
                    if len(grid) >= 502:
                        raise ValueError("Importa un máximo de 500 filas por archivo.")
                    if row[50] is not None:
                        raise ValueError("Admitimos hasta 50 columnas por hoja.")
                    grid.append(list(row[:50]))
            finally:
                book.close()
        except ValueError:
            raise
        except Exception:
            raise ValueError(
                "No se reconoce el Excel. Guarda el archivo como .xlsx sin contraseña."
            )
    else:
        raise ValueError("Selecciona un archivo .xlsx o .csv.")
    grid = [[cell_text(v) for v in row] for row in grid]
    while grid and not any(grid[-1]):
        grid.pop()
    if len(grid) < 2:
        raise ValueError(
            "La primera fila debe contener cabeceras y después al menos un registro."
        )
    headers = grid[0]
    while headers and not headers[-1]:
        headers.pop()
    if not headers or len(headers) > 50:
        raise ValueError("Admitimos entre 1 y 50 columnas.")
    if any(not h or len(h) > 160 or h.startswith("=") for h in headers):
        raise ValueError(
            "Todas las columnas necesitan una cabecera de texto de hasta 160 caracteres."
        )
    if len(set(normalized(h) for h in headers)) != len(headers):
        raise ValueError("Hay cabeceras repetidas; dales nombres distintos.")
    records = []
    for line, row in enumerate(grid[1:], 2):
        if not any(row):
            continue
        if any(row[len(headers) :]):
            raise ValueError(f"La fila {line} tiene más celdas que cabeceras.")
        records.append(
            {"line": line, "cells": (row + [""] * len(headers))[: len(headers)]}
        )
    if not records or len(records) > 500:
        raise ValueError("Importa entre 1 y 500 filas por archivo.")
    suggestions = {}
    for key, aliases in ALIASES.items():
        matches = [
            str(i)
            for i, h in enumerate(headers)
            if normalized(h) in [normalized(a) for a in aliases]
        ]
        suggestions[key] = matches[0] if len(matches) == 1 else ""
    return content, dict(
        headers=headers,
        rows=records,
        sheets=sheets,
        sheet=selected,
        mapping=suggestions,
    )


def import_date(value):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Fecha no válida: usa AAAA-MM-DD o DD/MM/AAAA.")


def import_quantity(value):
    value = value.replace(" ", "").replace("\u00a0", "")
    if "," in value and "." in value:
        value = (
            value.replace(".", "").replace(",", ".")
            if value.rfind(",") > value.rfind(".")
            else value.replace(",", "")
        )
    else:
        value = value.replace(",", ".")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError("Cantidad no válida.")
    if not result.is_finite() or result < 0 or result > Decimal("1e14"):
        raise ValueError("Cantidad fuera del intervalo permitido.")
    return str(result)


def category(value):
    key = normalized(value)
    names = {
        "electricity": "electricity",
        "electricidad": "electricity",
        "gas": "gas",
        "gas natural": "gas",
        "natural gas": "gas",
        "diesel": "diesel",
        "gasoleo": "diesel",
        "petrol": "petrol",
        "gasolina": "petrol",
        "gasoline": "petrol",
    }
    names.update({normalized(k): k for k in ACTIVITIES})
    names.update({normalized(v.label): k for k, v in ACTIVITIES.items()})
    if key not in names:
        raise ValueError(
            "Categoría no admitida. Consulta el catálogo de la plantilla de ALgyre."
        )
    return names[key]


def own_template():
    book = Workbook()
    ws = book.active
    ws.title = "Consumos"
    ws.append(list(FIELDS.values()))
    ws.append(
        [
            "Nombre de tu instalación",
            "electricity",
            1250.5,
            "kWh",
            "2026-01-01",
            "2026-01-31",
            "",
            "FACT-001",
            "",
            "",
        ]
    )
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 25
    guide = book.create_sheet("Ayuda")
    for row in [
        [
            "ALgyre · plantilla propia de consumos",
            "Sustituye la fila de ejemplo por tus datos.",
        ],
        ["Categorías", ", ".join(ACTIVITIES)],
        ["Unidades", ", ".join(UNIT_LABELS)],
        [
            "Fechas",
            "AAAA-MM-DD o DD/MM/AAAA. Un periodo por fila dentro del mismo año.",
        ],
        ["Instalación", "Debe existir en ALgyre y tener la categoría activada."],
        ["Documento PDF", "Nombre exacto de un PDF ya guardado. Es opcional."],
        ["Decimales", "Números de Excel o texto con coma decimal; no uses fórmulas."],
    ]:
        guide.append(row)
    for key, activity in ACTIVITIES.items():
        guide.append(
            [
                key,
                f'{activity.label} · Alcance {activity.scope} · Unidades: {", ".join(activity.units)}. {activity.guidance}',
            ]
        )
    guide.append(
        [
            "Factores específicos",
            "Las nuevas actividades se importan pendientes: abre Revisar y elige el factor. Describe actividad y límites en Notas.",
        ]
    )
    guide.column_dimensions["A"].width = 42
    guide.column_dimensions["B"].width = 95
    out = io.BytesIO()
    book.save(out)
    book.close()
    return out.getvalue()
