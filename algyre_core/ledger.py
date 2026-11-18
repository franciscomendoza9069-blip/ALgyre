"""Ledger validation, calculations and reporting snapshots."""

import calendar
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from flask import session
from .common import (
    now,
    uid,
    dumps,
    rows,
    one,
    event,
    insert,
    text,
    number,
    checked_year,
)
from .environment import (
    CAT,
    ACTIVITIES,
    UNIT_LABELS,
    catalog,
    valid_unit,
    normalize_quantity,
)


def match_factor(db, r):
    f = one(db, "SELECT * FROM facilities WHERE id=?", (r["facility_id"],))
    unit = normalize_quantity(r["quantity"], r["unit"])[1]
    activity = ACTIVITIES[r["category"]]
    if activity.explicit_factor and not r.get("factor_id"):
        return None, "Selecciona un factor específico para esta actividad"
    params = (r["category"], f["country"], int(r["start"][:4]), unit)
    fs = rows(
        db,
        "SELECT * FROM factors WHERE category=? AND country=? AND year=? AND unit=? AND method IN ('location','activity') AND validated=1",
        params,
    )
    if r["category"] == "electricity":
        fs = [v for v in fs if v["method"] == "location"]
    if r.get("factor_id"):
        fs = [v for v in fs if v["id"] == r["factor_id"]]
    if len(fs) != 1:
        return None, (
            "Sin factor compatible" if not fs else "Selecciona una versión del factor"
        )
    return fs[0], ""


def calculate(db, r):
    factor, why = match_factor(db, r)
    if not factor:
        return None
    q, _ = normalize_quantity(r["quantity"], r["unit"])
    kg = q * Decimal(factor["value"])
    calc = dict(
        id=uid(),
        consumption_id=r["id"],
        revision=r["revision"],
        factor_id=factor["id"],
        normalized_quantity=str(q),
        kg_co2e=str(kg),
        engine="algyre-2.0",
        created_at=now(),
    )
    db.execute(
        "INSERT OR IGNORE INTO calculations VALUES(?,?,?,?,?,?,?,?)",
        tuple(calc.values()),
    )
    return kg


def validate_record(db, d, existing_id=None):
    f = one(db, "SELECT * FROM facilities WHERE id=?", (d.get("facility_id"),))
    if not f:
        raise ValueError("Elige una instalación.")
    if f["archived"] and not existing_id:
        raise ValueError("La instalación está archivada.")
    cat = d.get("category")
    if cat not in CAT:
        raise ValueError("Categoría no admitida.")
    if cat not in json.loads(f["categories"]):
        raise ValueError(
            "Activa esta categoría en la instalación antes de añadir datos."
        )
    unit = d.get("unit")
    if not valid_unit(cat, unit):
        raise ValueError("Unidad incompatible con la categoría.")
    a = date.fromisoformat(d.get("start", ""))
    b = date.fromisoformat(d.get("end", ""))
    if a > b or a.year != b.year:
        raise ValueError(
            "Usa un intervalo dentro del mismo año, con inicio anterior al fin. Divide las facturas entre años y documenta el reparto."
        )
    checked_year(a.year)
    ref = text(d.get("reference"), 160)
    dup = rows(
        db,
        "SELECT * FROM consumptions WHERE facility_id=? AND category=? AND start<=? AND end>=? AND id!=?",
        (f["id"], cat, b.isoformat(), a.isoformat(), existing_id or ""),
    )
    if ref and one(
        db,
        "SELECT id FROM consumptions WHERE facility_id=? AND reference=? AND category=? AND id!=?",
        (f["id"], ref, cat, existing_id or ""),
    ):
        raise ValueError(
            "Ya existe esa referencia de factura para esta instalación y categoría."
        )
    if not ACTIVITIES[cat].continuous:
        quantity, normalized_unit = normalize_quantity(
            number(d.get("quantity", "")), unit
        )
        # Events can legitimately share dates. Still flag identical activities
        # without distinct references so imports do not silently double count.
        dup = [
            row
            for row in dup
            if row["start"] == a.isoformat()
            and row["end"] == b.isoformat()
            and normalize_quantity(row["quantity"], row["unit"])
            == (quantity, normalized_unit)
            and row["supplier"] == text(d.get("supplier"), 160)
            and not (ref and row["reference"] and ref != row["reference"])
        ]
    if dup and not d.get("allow_overlap"):
        raise ValueError(
            "Hay un suministro solapado o una actividad posiblemente duplicada. Revisa los datos y confirma la excepción si son actividades distintas."
        )
    if dup and not text(d.get("note"), 2000):
        raise ValueError("Indica en las notas el motivo del solapamiento.")
    doc = d.get("document_id") or None
    if doc and not one(db, "SELECT id FROM documents WHERE id=?", (doc,)):
        raise ValueError("Documento no encontrado.")
    r = dict(
        facility_id=f["id"],
        document_id=doc,
        category=cat,
        quantity=str(number(d.get("quantity", ""))),
        unit=unit,
        start=a.isoformat(),
        end=b.isoformat(),
        supplier=text(d.get("supplier"), 160),
        reference=ref,
        factor_id=d.get("factor_id") or None,
        note=text(d.get("note"), 2000),
        estimated=int(bool(d.get("estimated"))),
    )
    if r["factor_id"] and not match_factor(db, r)[0]:
        raise ValueError(
            "El factor seleccionado no coincide con país, año, categoría y unidad."
        )
    if ACTIVITIES[cat].explicit_factor and not r["note"]:
        raise ValueError(
            "Describe la actividad, el método y los límites del factor en las notas."
        )
    if r["estimated"] and not r["note"]:
        raise ValueError("Describe el supuesto utilizado para esta estimación.")
    return r


def save_record(db, d, rid=None):
    before = one(db, "SELECT * FROM consumptions WHERE id=?", (rid,)) if rid else None
    if rid and not before:
        raise ValueError("Consumo no encontrado.")
    if before and int(d.get("revision", 0)) != before["revision"]:
        raise ValueError(
            "Este consumo ha cambiado en otra pestaña. Recarga antes de editar."
        )
    r = validate_record(db, d, rid)
    stamp = now()
    if before:
        if not text(d.get("reason")):
            raise ValueError("Describe el motivo de la corrección.")
        r.update(revision=before["revision"] + 1, updated_at=stamp)
        db.execute(
            "UPDATE consumptions SET " + ",".join(k + "=?" for k in r) + " WHERE id=?",
            list(r.values()) + [rid],
        )
    else:
        rid = uid()
        r.update(id=rid, revision=1, created_at=stamp, updated_at=stamp)
        insert(db, "consumptions", r)
    result = one(db, "SELECT * FROM consumptions WHERE id=?", (rid,))
    calculate(db, result)
    event(
        db,
        "consumption",
        rid,
        "corrected" if before else "created",
        before,
        result,
        text(d.get("reason")),
    )
    return rid


def state(db, year):
    company = one(db, "SELECT * FROM company WHERE id=1")
    facilities = rows(db, "SELECT * FROM facilities ORDER BY archived,name")
    factors = rows(db, "SELECT * FROM factors ORDER BY created_at DESC")
    docs = rows(
        db,
        "SELECT id,name,hash,extracted,created_at FROM documents ORDER BY created_at DESC",
    )
    records = rows(
        db,
        "SELECT c.*,f.name facility_name,f.country FROM consumptions c JOIN facilities f ON f.id=c.facility_id WHERE substr(c.start,1,4)=? ORDER BY c.start DESC",
        (str(year),),
    )
    months = [Decimal(0) for _ in range(12)]
    total = Decimal(0)
    scopes = {"1": Decimal(0), "2": Decimal(0), "3": Decimal(0)}
    for r in records:
        r["scope"] = ACTIVITIES[r["category"]].scope
        r["scope3_category"] = ACTIVITIES[r["category"]].scope3_category
        fac, why = match_factor(db, r)
        r["factor"] = fac
        r["pending_reason"] = why
        r["document_name"] = next(
            (v["name"] for v in docs if v["id"] == r["document_id"]), None
        )
        calc = (
            one(
                db,
                "SELECT * FROM calculations WHERE consumption_id=? AND revision=? AND factor_id=?",
                (r["id"], r["revision"], fac["id"]),
            )
            if fac
            else None
        )
        r["kg_co2e"] = calc["kg_co2e"] if calc else None
        if not calc:
            if fac:
                r["pending_reason"] = "Cálculo pendiente"
            continue
        kg = Decimal(calc["kg_co2e"])
        total += kg
        scopes[str(r["scope"])] += kg
        a = date.fromisoformat(r["start"])
        b = date.fromisoformat(r["end"])
        days = (b - a).days + 1
        for m in range(1, 13):
            lo = max(a, date(year, m, 1))
            hi = min(b, date(year, m, calendar.monthrange(year, m)[1]))
            if hi >= lo:
                months[m - 1] += kg * Decimal((hi - lo).days + 1) / days
    gaps = []
    covered = 0
    expected = 0
    for f in facilities:
        # Archived sites with historical records remain in the historical coverage.
        if f["archived"] and not any(r["facility_id"] == f["id"] for r in records):
            continue
        for cat in json.loads(f["categories"]):
            if not ACTIVITIES[cat].continuous:
                continue
            for m in range(1, 13):
                expected += 1
                lo = date(year, m, 1)
                hi = date(year, m, calendar.monthrange(year, m)[1])
                spans = []
                for r in records:
                    if r["facility_id"] == f["id"] and r["category"] == cat:
                        a = max(lo, date.fromisoformat(r["start"]))
                        b = min(hi, date.fromisoformat(r["end"]))
                        if a <= b:
                            spans.append((a, b))
                cursor = lo
                for a, b in sorted(spans):
                    if a > cursor:
                        break
                    if b >= cursor:
                        cursor = b + timedelta(days=1)
                if cursor > hi:
                    covered += 1
                else:
                    gaps.append(dict(facility=f["name"], category=CAT[cat], month=m))
    docs = [
        dict(
            v,
            extracted=json.loads(v["extracted"]),
            linked=sum(
                1
                for r in rows(db, "SELECT document_id FROM consumptions")
                if r["document_id"] == v["id"]
            ),
        )
        for v in docs
    ]
    # Inputs that affect totals, reporting boundaries, or coverage invalidate previous reports.
    fp = hashlib.sha256(
        dumps(dict(company=company, facilities=facilities, records=records)).encode()
    ).hexdigest()
    reports = rows(
        db,
        "SELECT id,name,year,fingerprint,created_at FROM reports WHERE year=? ORDER BY created_at DESC",
        (year,),
    )
    for rep in reports:
        rep["stale"] = rep["fingerprint"] != fp
    return dict(
        catalog=catalog(),
        units=UNIT_LABELS,
        company=company,
        facilities=facilities,
        factors=factors,
        documents=docs,
        records=records,
        summary=dict(
            total=str(total),
            scope1=str(scopes["1"]),
            scope2=str(scopes["2"]),
            scope3=str(scopes["3"]),
            monthly=[str(x) for x in months],
            pending=sum(r["kg_co2e"] is None for r in records),
            covered=covered,
            expected=expected,
            gaps=gaps,
        ),
        reports=reports,
        events=rows(db, "SELECT * FROM events ORDER BY rowid DESC LIMIT 100"),
        fingerprint=fp,
        year=year,
        demo=bool(session.get("demo")),
    )
