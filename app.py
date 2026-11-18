"""ALgyre HTTP routes and application composition for local and company deployments."""

import base64
import calendar
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone
from decimal import InvalidOperation
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, Response, abort, g, jsonify, request, send_file, session
from algyre_core import intake

from algyre_core.common import (
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
    country,
)
from algyre_core.environment import CAT, UNIT_LABELS, valid_unit
from algyre_core.ledger import (
    match_factor,
    calculate,
    save_record,
    state,
)
from algyre_core.reporting import pdf_report
from algyre_core.documents import extract_pdf
from algyre_core.migrations import migrate_ledger
from algyre_core.compatibility import load_legacy_environment, local_database

load_legacy_environment()

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("ALGYRE_DATA_DIR", str(ROOT / "data"))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
app = Flask(__name__, static_folder="static")
app.config.update(
    SECRET_KEY=secrets.token_hex(32),
    MAX_CONTENT_LENGTH=24 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
MULTI = os.environ.get("ALGYRE_MODE", "local") == "public"
app.config["MULTI_TENANT"] = MULTI
LOCK = threading.RLock()
ATTEMPTS = []
IMPORTS = {}
UPLOADS = {}

TABLES = [
    "company",
    "facilities",
    "factors",
    "documents",
    "consumptions",
    "calculations",
    "events",
    "reports",
]


@contextmanager
def connect(path=None):
    if path is None and app.config["MULTI_TENANT"]:
        path = getattr(g, "ledger_path", None)
        if path is None:
            abort(403, description="Selecciona una empresa autorizada.")
    db = sqlite3.connect(
        path or (DATA / "demo.sqlite" if session.get("demo") else local_database(DATA)),
        timeout=20,
    )
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path):
    with connect(path) as db:
        schema = (ROOT / "algyre_core" / "schema.sql").read_text("utf-8")
        db.executescript(schema)
        migrate_ledger(db, path, schema)
        db.execute(
            "INSERT OR IGNORE INTO company VALUES(1,?,?,?,?,?,?)",
            ("Mi empresa", "", "", "", 2026, now()),
        )


def dto():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Se esperaba un objeto JSON.")
    return data


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 600000
    ).hex()


def login_session(demo=False):
    session.clear()
    session.update(auth=True, demo=demo, csrf=secrets.token_hex(24), sid=uid())
    session.permanent = True


@app.before_request
def guard():
    if app.config["MULTI_TENANT"]:
        return accounts.guard()
    if request.host.split(":")[0] not in ("127.0.0.1", "localhost"):
        return jsonify(error="Este espacio solo admite acceso local."), 403
    if request.method == "POST":
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            return jsonify(error="Origen de solicitud no permitido."), 403
    if request.path.startswith("/api/") and request.path not in (
        "/api/status",
        "/api/setup",
        "/api/login",
        "/api/demo",
    ):
        if not session.get("auth"):
            return jsonify(error="Inicia sesión para continuar."), 401
        if request.method == "POST" and not hmac.compare_digest(
            request.headers.get("X-CSRF-Token", ""), session.get("csrf", "missing")
        ):
            return jsonify(error="La sesión ha caducado. Recarga la página."), 403


@app.after_request
def security(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(ValueError)
def bad_value(e):
    return jsonify(error=str(e)), 400


@app.errorhandler(sqlite3.IntegrityError)
def bad_constraint(e):
    return (
        jsonify(error="No se pudo guardar: registro duplicado o relación inválida."),
        409,
    )


@app.errorhandler(413)
def too_large(e):
    return (
        jsonify(
            error="El archivo supera el tamaño permitido (15 MB por PDF; 24 MB por solicitud)."
        ),
        413,
    )


@app.errorhandler(500)
def internal(e):
    return (
        jsonify(
            error="No se pudo completar la operación. Tus datos guardados se conservan."
        ),
        500,
    )


@app.get("/")
def index():
    return send_file(ROOT / "static" / "index.html")


@app.get("/api/status")
def status():
    if app.config["MULTI_TENANT"]:
        return accounts.status()
    with connect(local_database(DATA)) as db:
        configured = bool(one(db, "SELECT id FROM auth"))
    return jsonify(
        configured=configured,
        authenticated=bool(session.get("auth")),
        demo=bool(session.get("demo")),
        csrf=session.get("csrf"),
    )


@app.post("/api/setup")
def setup():
    if app.config["MULTI_TENANT"]:
        return jsonify(error="El administrador se crea desde el servidor."), 403
    d = dto()
    pw = str(d.get("password", ""))
    if not 10 <= len(pw) <= 200:
        raise ValueError("Elige una contraseña de 10 a 200 caracteres.")
    with LOCK, connect(local_database(DATA)) as db:
        if one(db, "SELECT id FROM auth"):
            return jsonify(error="El espacio ya tiene contraseña."), 409
        salt = secrets.token_hex(16)
        db.execute("INSERT INTO auth VALUES(1,?,?)", (salt, password_hash(pw, salt)))
    login_session()
    return jsonify(ok=True, csrf=session["csrf"])


@app.post("/api/login")
def login():
    if app.config["MULTI_TENANT"]:
        return accounts.login()
    d = dto()
    stamp = time.time()
    with LOCK:
        ATTEMPTS[:] = [v for v in ATTEMPTS if stamp - v < 60]
        if len(ATTEMPTS) >= 5:
            return jsonify(error="Demasiados intentos. Espera un minuto."), 429
        ATTEMPTS.append(stamp)
    with connect(local_database(DATA)) as db:
        auth = one(db, "SELECT * FROM auth")
    pw = str(d.get("password", ""))
    if (
        len(pw) > 200
        or not auth
        or not hmac.compare_digest(
            password_hash(pw, auth["salt"]), auth["password_hash"]
        )
    ):
        return jsonify(error="Contraseña incorrecta."), 401
    with LOCK:
        ATTEMPTS.clear()
    login_session()
    return jsonify(ok=True, csrf=session["csrf"])


@app.post("/api/logout")
def logout():
    if app.config["MULTI_TENANT"]:
        return accounts.logout()
    session.clear()
    return jsonify(ok=True)


@app.post("/api/demo")
def demo():
    if app.config["MULTI_TENANT"]:
        return jsonify(error="El ejemplo compartido está desactivado."), 403
    login_session(True)
    return jsonify(ok=True, csrf=session["csrf"])


@app.get("/api/state")
def get_state():
    year = checked_year(request.args.get("year", 2026))
    with LOCK, connect() as db:
        return jsonify(state(db, year))


@app.post("/api/company")
def company_save():
    d = dto()
    name = text(d.get("name"), 160)
    if not name:
        raise ValueError("Escribe el nombre de la empresa.")
    with LOCK, connect() as db:
        old = one(db, "SELECT * FROM company")
        db.execute(
            "UPDATE company SET name=?,country=?,boundary=?,exclusions=?,year=?,updated_at=? WHERE id=1",
            (
                name,
                country(d.get("country")),
                text(d.get("boundary"), 4000),
                text(d.get("exclusions"), 4000),
                checked_year(d.get("year")),
                now(),
            ),
        )
        event(db, "company", "1", "updated", old, one(db, "SELECT * FROM company"))
    if app.config["MULTI_TENANT"]:
        with accounts.db() as identity:
            identity.execute(
                "UPDATE organizations SET name=? WHERE id=?",
                (name, g.organization["id"]),
            )
    return jsonify(ok=True)


@app.post("/api/facilities")
@app.post("/api/facilities/<rid>")
def facility_save(rid=None):
    d = dto()
    cats = d.get("categories", [])
    name = text(d.get("name"), 160)
    if (
        not name
        or not isinstance(cats, list)
        or not cats
        or any(c not in CAT for c in cats)
    ):
        raise ValueError("Introduce un nombre y al menos una categoría.")
    ownership = d.get("ownership", "owned")
    if ownership not in ("owned", "rented"):
        raise ValueError("Titularidad no válida.")
    with LOCK, connect() as db:
        old = one(db, "SELECT * FROM facilities WHERE id=?", (rid,)) if rid else None
        if rid and not old:
            raise ValueError("Instalación no encontrada.")
        r = dict(
            name=name,
            country=country(d.get("country")),
            ownership=ownership,
            categories=dumps(list(dict.fromkeys(cats))),
            archived=int(bool(d.get("archived"))),
            updated_at=now(),
        )
        if old:
            if old["country"] != r["country"] and one(
                db, "SELECT id FROM consumptions WHERE facility_id=?", (rid,)
            ):
                raise ValueError(
                    "Una instalación con consumos no puede cambiar de país. Crea otra instalación."
                )
            used = {
                v["category"]
                for v in rows(
                    db,
                    "SELECT DISTINCT category FROM consumptions WHERE facility_id=?",
                    (rid,),
                )
            }
            if not used.issubset(set(cats)):
                raise ValueError("Conserva las categorías con registros históricos.")
            db.execute(
                "UPDATE facilities SET "
                + ",".join(k + "=?" for k in r)
                + " WHERE id=?",
                list(r.values()) + [rid],
            )
        else:
            rid = uid()
            r.update(id=rid, created_at=now())
            insert(db, "facilities", r)
        event(db, "facility", rid, "updated" if old else "created", old, r)
    return jsonify(ok=True, id=rid)


@app.post("/api/factors")
def factor_save():
    d = dto()
    cat = d.get("category")
    unit = d.get("unit")
    value = number(d.get("value", ""))
    source = text(d.get("source"), 1000)
    if not valid_unit(cat, unit, factor=True):
        raise ValueError("Categoría o unidad de factor no válida.")
    if urlparse(source).scheme not in ("http", "https") or not urlparse(source).netloc:
        raise ValueError("Incluye la URL de la fuente del factor.")
    if not d.get("validated"):
        raise ValueError("Confirma que has comprobado la metodología y el factor.")
    r = dict(
        id=uid(),
        name=text(d.get("name"), 160),
        category=cat,
        country=country(d.get("country")),
        year=checked_year(d.get("year")),
        unit=unit,
        value=str(value),
        source=source,
        version=text(d.get("version"), 100),
        license=text(d.get("license"), 300),
        validated=1,
        method="location" if cat == "electricity" else "activity",
        created_at=now(),
        updated_at=now(),
    )
    if not all(r[k] for k in ("name", "version", "license")):
        raise ValueError("Completa nombre, versión y condiciones de uso.")
    with LOCK, connect() as db:
        insert(db, "factors", r)
        event(db, "factor", r["id"], "created", after=r)
        for rec in rows(db, "SELECT * FROM consumptions"):
            calculate(db, rec)
    return jsonify(ok=True, id=r["id"])


@app.post("/api/consumptions")
@app.post("/api/consumptions/<rid>")
def record_save(rid=None):
    d = dto()
    if not d.get("reviewed"):
        raise ValueError("Confirma que has revisado el consumo.")
    with LOCK, connect() as db:
        rid = save_record(db, d, rid)
    return jsonify(ok=True, id=rid)


@app.post("/api/documents")
def upload():
    d = dto()
    name = text(d.get("name"), 200)
    try:
        content = base64.b64decode(d.get("content", ""), validate=True)
    except Exception:
        raise ValueError("Archivo no válido.")
    if not content.startswith(b"%PDF-") or len(content) > 15 * 1024 * 1024:
        raise ValueError("Selecciona un PDF de hasta 15 MB.")
    digest = hashlib.sha256(content).hexdigest()
    with LOCK, connect() as db:
        existing = one(db, "SELECT id FROM documents WHERE hash=?", (digest,))
        if existing:
            return (
                jsonify(
                    error="Esta factura ya está guardada. Abre el documento existente.",
                    existing_id=existing["id"],
                ),
                409,
            )
        body, suggestions = extract_pdf(content)
        rid = uid()
        db.execute(
            "INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)",
            (rid, name, digest, content, body, dumps(suggestions), now(), now()),
        )
        event(db, "document", rid, "uploaded", after={"name": name, "hash": digest})
    return jsonify(ok=True, id=rid, extracted=suggestions)


@app.get("/api/documents/<rid>/file")
def document_file(rid):
    with connect() as db:
        doc = one(db, "SELECT name,content FROM documents WHERE id=?", (rid,))
    if not doc:
        return jsonify(error="Documento no encontrado."), 404
    return send_file(
        io.BytesIO(doc["content"]),
        mimetype="application/pdf",
        download_name=doc["name"],
        as_attachment=True,
    )


CSV_FIELDS = [
    "instalacion",
    "categoria",
    "cantidad",
    "unidad",
    "inicio",
    "fin",
    "proveedor",
    "referencia",
    "notas",
]


@app.get("/api/template.csv")
def template():
    return csv_response(
        [
            dict(
                zip(
                    CSV_FIELDS,
                    [
                        "Nombre de tu instalación",
                        "electricity",
                        "1250,5",
                        "kWh",
                        "2026-01-01",
                        "2026-01-31",
                        "",
                        "FACT-001",
                        "",
                    ],
                )
            )
        ],
        CSV_FIELDS,
        "plantilla-consumos.csv",
    )


def csv_response(values, fields, name):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(
        out, fieldnames=fields, delimiter=";", extrasaction="ignore"
    )
    writer.writeheader()
    for r in values:
        safe = {
            k: (
                "'" + str(v)
                if str(v).startswith(("=", "+", "-", "@", "\t", "\r"))
                else v
            )
            for k, v in r.items()
        }
        writer.writerow(safe)
    return Response(
        "\ufeff" + out.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.post("/api/import/preview")
def preview_csv():
    d = dto()
    body = str(d.get("text", ""))
    if len(body) > 2_000_000:
        raise ValueError("El CSV supera 2 MB.")
    try:
        dialect = csv.Sniffer().sniff(body[:4096], delimiters=";,\t")
    except csv.Error:
        raise ValueError("No se reconoce el CSV. Descarga y utiliza la plantilla.")
    reader = csv.DictReader(io.StringIO(body.lstrip("\ufeff")), dialect=dialect)
    if not set(CSV_FIELDS[:6]).issubset(reader.fieldnames or []):
        raise ValueError(
            "Faltan columnas. Usa la plantilla: instalacion, categoria, cantidad, unidad, inicio y fin."
        )
    output = []
    good = []
    with connect() as source:
        # Dry run on a transactionally consistent in-memory copy catches duplicates within this file.
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        source.backup(db)
        db.execute("PRAGMA foreign_keys=ON")
        try:
            for n, row in enumerate(reader, 2):
                if n > 501:
                    raise ValueError("Importa un máximo de 500 filas por archivo.")
                f = one(
                    db,
                    "SELECT id FROM facilities WHERE name=? AND archived=0",
                    (row.get("instalacion", "").strip(),),
                )
                v = dict(
                    facility_id=f["id"] if f else "",
                    category=row.get("categoria"),
                    quantity=row.get("cantidad"),
                    unit=row.get("unidad"),
                    start=row.get("inicio"),
                    end=row.get("fin"),
                    supplier=row.get("proveedor"),
                    reference=row.get("referencia"),
                    note=row.get("notas"),
                    reviewed=True,
                )
                try:
                    save_record(db, v)
                    good.append(v)
                    error = ""
                except (ValueError, sqlite3.IntegrityError) as e:
                    error = str(e)
                output.append(
                    dict(
                        line=n,
                        facility=row.get("instalacion"),
                        quantity=row.get("cantidad"),
                        error=error,
                    )
                )
        finally:
            db.close()
    token = secrets.token_hex(24)
    with LOCK:
        for k in list(IMPORTS):
            if time.time() - IMPORTS[k]["time"] > 1800:
                del IMPORTS[k]
        IMPORTS[token] = dict(
            sid=session["sid"],
            time=time.time(),
            records=good,
            errors=any(r["error"] for r in output),
        )
    return jsonify(rows=output, token=token, count=len(good))


@app.post("/api/import/confirm")
def confirm_import():
    d = dto()
    if not d.get("reviewed"):
        raise ValueError("Confirma que has revisado las filas.")
    with LOCK:
        data = IMPORTS.get(d.get("token"))
        if (
            not data
            or data["sid"] != session["sid"]
            or time.time() - data["time"] > 1800
        ):
            raise ValueError(
                "La previsualización ha caducado. Vuelve a cargar el archivo."
            )
        if data["errors"] or not data["records"]:
            raise ValueError("Corrige todos los errores antes de importar.")
        with connect() as db:
            ids = []
            for index, r in enumerate(data["records"]):
                provenance = data.get("source")
                if provenance:
                    r = dict(
                        r,
                        reason=f"Importación {provenance['name']} · fila {data['lines'][index]} · lote {d['token']}",
                    )
                ids.append(save_record(db, r))
            if data.get("source"):
                event(
                    db,
                    "import",
                    d["token"],
                    "imported",
                    after=dict(
                        data["source"],
                        count=len(ids),
                        record_ids=ids,
                        lines=data["lines"],
                    ),
                    reason="Archivo revisado y confirmado",
                )
        del IMPORTS[d["token"]]
    return jsonify(
        ok=True,
        count=len(data["records"]),
        years=sorted({int(r["start"][:4]) for r in data["records"]}),
    )


def staged_upload(token):
    item = UPLOADS.get(token)
    if not item or item["sid"] != session["sid"] or time.time() - item["time"] > 1800:
        raise ValueError("El archivo ha caducado. Vuelve a seleccionarlo.")
    return item


@app.get("/api/template.xlsx")
def template_excel():
    return send_file(
        io.BytesIO(intake.own_template()),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="algyre-consumos.xlsx",
    )


@app.post("/api/import/inspect")
def inspect_upload():
    d = dto()
    name = text(d.get("name"), 200)
    raw, parsed = intake.read_upload(name, d.get("content"), d.get("sheet"))
    token = secrets.token_hex(24)
    with LOCK:
        for cache in (UPLOADS, IMPORTS):
            for key in list(cache):
                if time.time() - cache[key]["time"] > 1800:
                    del cache[key]
        if len(UPLOADS) >= 20:
            del UPLOADS[next(iter(UPLOADS))]
        UPLOADS[token] = dict(
            sid=session["sid"],
            time=time.time(),
            source=dict(
                name=name, sha256=hashlib.sha256(raw).hexdigest(), sheet=parsed["sheet"]
            ),
            **parsed,
        )
    return jsonify(
        token=token,
        headers=parsed["headers"],
        sheets=parsed["sheets"],
        sheet=parsed["sheet"],
        mapping=parsed["mapping"],
        sample=parsed["rows"][:3],
        count=len(parsed["rows"]),
    )


@app.post("/api/import/validate")
def validate_upload():
    d = dto()
    with LOCK:
        upload = staged_upload(d.get("token"))
        mapping = d.get("mapping")
        defaults = d.get("defaults", {})
        if not isinstance(mapping, dict) or not isinstance(defaults, dict):
            raise ValueError("Revisa la asignación de columnas.")
        selected = {}
        for key in intake.FIELDS:
            value = mapping.get(key, "")
            if value not in ("", None):
                if not str(value).isdigit() or not 0 <= int(value) < len(
                    upload["headers"]
                ):
                    raise ValueError("Columna no válida.")
                selected[key] = int(value)
        if len(set(selected.values())) != len(selected):
            raise ValueError("Asigna cada columna a un único campo.")
        for key in ("quantity", "start", "end"):
            if key not in selected:
                raise ValueError("Asigna las columnas de cantidad, inicio y fin.")
        edits = d.get("edits", {})
        if not isinstance(edits, dict) or len(edits) > 500:
            raise ValueError("Correcciones no válidas.")
        output = []
        good = []
        lines = []
        with connect() as source:
            db = sqlite3.connect(":memory:")
            db.row_factory = sqlite3.Row
            source.backup(db)
            db.execute("PRAGMA foreign_keys=ON")
            try:
                for row in upload["rows"]:
                    v = {key: row["cells"][idx] for key, idx in selected.items()}
                    for key in ("facility", "category", "unit"):
                        v.setdefault(key, text(defaults.get(key)))
                    changes = edits.get(str(row["line"]), {})
                    if not isinstance(changes, dict) or any(
                        k not in intake.FIELDS for k in changes
                    ):
                        raise ValueError("Corrección de fila no válida.")
                    v.update({k: text(val, 2000) for k, val in changes.items()})
                    error = ""
                    warnings = []
                    candidate = None
                    try:
                        if any(str(val).startswith("=") for val in v.values()):
                            raise ValueError(
                                "Sustituye las fórmulas por valores antes de importar."
                            )
                        cat = intake.category(v.get("category", ""))
                        unit = {
                            "kwh": "kWh",
                            "mwh": "MWh",
                            "l": "L",
                            "litros": "L",
                            "liters": "L",
                            "kg": "kg",
                            "m3": "m3",
                            "m³": "m3",
                            **{u.lower(): u for u in UNIT_LABELS},
                        }.get(v.get("unit", "").lower())
                        if not v.get("unit") and cat == "electricity":
                            unit = "kWh"
                            warnings.append(
                                "Unidad no indicada: se utilizará kWh. Confírmala."
                            )
                        if not unit:
                            raise ValueError(
                                "Indica una unidad del catálogo compatible con esta actividad."
                            )
                        facility = one(
                            db,
                            "SELECT id FROM facilities WHERE name=? AND archived=0",
                            (v.get("facility", ""),),
                        )
                        document = None
                        if v.get("document"):
                            matches = rows(
                                db,
                                "SELECT id FROM documents WHERE name=?",
                                (v["document"],),
                            )
                            if len(matches) != 1:
                                raise ValueError(
                                    "El PDF debe coincidir con un único documento ya guardado."
                                )
                            document = matches[0]["id"]
                        candidate = dict(
                            facility_id=facility["id"] if facility else "",
                            category=cat,
                            quantity=intake.import_quantity(v.get("quantity", "")),
                            unit=unit,
                            start=intake.import_date(v.get("start", "")),
                            end=intake.import_date(v.get("end", "")),
                            supplier=v.get("supplier", ""),
                            reference=v.get("reference", ""),
                            note=v.get("note", ""),
                            document_id=document,
                            reviewed=True,
                        )
                        save_record(db, candidate)
                        if not match_factor(db, candidate)[0]:
                            warnings.append(
                                "Sin un único factor compatible; quedará pendiente de cálculo."
                            )
                        if not document:
                            warnings.append("Sin PDF vinculado.")
                        v.update(
                            category=cat,
                            unit=unit,
                            quantity=candidate["quantity"],
                            start=candidate["start"],
                            end=candidate["end"],
                        )
                        good.append(candidate)
                        lines.append(row["line"])
                    except (ValueError, sqlite3.IntegrityError) as exc:
                        error = str(exc)
                    output.append(
                        dict(line=row["line"], values=v, error=error, warnings=warnings)
                    )
            finally:
                db.close()
        token = secrets.token_hex(24)
        # Only the latest validation for an upload can be confirmed, avoiding stale edited previews.
        for key in list(IMPORTS):
            if IMPORTS[key].get("upload") == d.get("token"):
                del IMPORTS[key]
        IMPORTS[token] = dict(
            sid=session["sid"],
            time=time.time(),
            records=good,
            lines=lines,
            errors=any(r["error"] for r in output),
            source=upload["source"],
            upload=d.get("token"),
        )
        ignored = [
            h for i, h in enumerate(upload["headers"]) if i not in selected.values()
        ]
    return jsonify(
        token=token,
        rows=output,
        count=len(good),
        errors=sum(bool(r["error"]) for r in output),
        ignored=ignored,
        source=upload["source"],
    )


@app.get("/api/consumptions/<rid>/history")
def record_history(rid):
    with connect() as db:
        record = one(db, "SELECT * FROM consumptions WHERE id=?", (rid,))
        if not record:
            return jsonify(error="Consumo no encontrado."), 404
        return jsonify(
            record=record,
            events=rows(
                db,
                "SELECT * FROM events WHERE entity='consumption' AND record_id=? ORDER BY rowid DESC",
                (rid,),
            ),
            imports=rows(
                db,
                "SELECT after_json,created_at FROM events WHERE entity='import' AND instr(after_json,?)>0 ORDER BY rowid DESC",
                (rid,),
            ),
        )


@app.get("/api/export.csv")
def export_csv():
    with LOCK, connect() as db:
        s = state(db, checked_year(request.args.get("year", 2026)))
    fields = [
        "instalacion",
        "alcance",
        "categoria_alcance3",
        "categoria",
        "cantidad",
        "unidad",
        "inicio",
        "fin",
        "referencia",
        "documento_id",
        "factor",
        "factor_valor",
        "factor_unidad",
        "factor_fuente",
        "factor_version",
        "kg_co2e",
        "estado",
        "revision",
        "notas",
    ]
    values = []
    for r in s["records"]:
        f = r["factor"] or {}
        values.append(
            dict(
                instalacion=r["facility_name"],
                alcance=r["scope"],
                categoria_alcance3=r["scope3_category"],
                categoria=r["category"],
                cantidad=r["quantity"],
                unidad=r["unit"],
                inicio=r["start"],
                fin=r["end"],
                referencia=r["reference"],
                documento_id=r["document_id"],
                factor=f.get("name"),
                factor_valor=f.get("value"),
                factor_unidad=f.get("unit"),
                factor_fuente=f.get("source"),
                factor_version=f.get("version"),
                kg_co2e=r["kg_co2e"],
                estado=r["pending_reason"] or "Calculado",
                revision=r["revision"],
                notas=r["note"],
            )
        )
    if s["demo"]:
        values.insert(
            0, dict(instalacion="EJEMPLO FICTICIO: NO UTILIZAR COMO DATOS REALES")
        )
    return csv_response(values, fields, "algyre-consumos.csv")


@app.post("/api/reports")
def report_create():
    d = dto()
    year = checked_year(d.get("year"))
    with LOCK, connect() as db:
        s = state(db, year)
        rid = uid()
        stamp = now()
        db.execute(
            "INSERT INTO reports VALUES(?,?,?,?,?,?)",
            (rid, year, f"Informe interno {year}", dumps(s), s["fingerprint"], stamp),
        )
        event(db, "report", rid, "created", after={"year": year})
    return jsonify(ok=True, id=rid)


@app.get("/api/reports/<rid>/pdf")
def report_pdf(rid):
    with connect() as db:
        r = one(db, "SELECT * FROM reports WHERE id=?", (rid,))
    if not r:
        return jsonify(error="Informe no encontrado."), 404
    return send_file(
        io.BytesIO(pdf_report(json.loads(r["snapshot"]), r["created_at"])),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f'algyre-informe-{r["year"]}.pdf',
    )


def backup_bytes(db):
    tables = {t: rows(db, f"SELECT * FROM {t}") for t in TABLES}
    for r in tables["documents"]:
        r["content"] = base64.b64encode(r["content"]).decode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "algyre.json",
            dumps(
                {
                    "format": "algyre-1",
                    "workspace": "demo" if session.get("demo") else "private",
                    "tables": tables,
                }
            ),
        )
    return out.getvalue()


@app.get("/api/backup")
def backup():
    with LOCK, connect() as db:
        content = backup_bytes(db)
    return send_file(
        io.BytesIO(content),
        mimetype="application/zip",
        as_attachment=True,
        download_name="algyre-copia.zip",
    )


@app.post("/api/restore")
def restore():
    d = dto()
    if d.get("confirmation") != "RESTAURAR":
        raise ValueError("Escribe RESTAURAR para sustituir los datos con la copia.")
    try:
        raw = base64.b64decode(d.get("content", ""), validate=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if (
                len(z.namelist()) != 1
                or z.namelist()[0] not in ("algyre.json", "linde.json")
                or z.getinfo(z.namelist()[0]).file_size > 80 * 1024 * 1024
            ):
                raise ValueError("Contenido de copia no válido o demasiado grande.")
            payload = json.loads(z.read(z.namelist()[0]))
    except Exception:
        raise ValueError("No se reconoce la copia ZIP de ALgyre.")
    if payload.get("format") not in ("algyre-1", "linde-1") or set(
        payload.get("tables", {})
    ) != set(TABLES):
        raise ValueError("Versión de copia no compatible.")
    if payload.get("workspace") != ("demo" if session.get("demo") else "private"):
        raise ValueError(
            "No se pueden mezclar copias del ejemplo con el espacio privado."
        )
    # Validate in staging using the real constraints before touching live data.
    stage = sqlite3.connect(":memory:")
    stage.row_factory = sqlite3.Row
    stage.executescript((ROOT / "algyre_core" / "schema.sql").read_text("utf-8"))
    try:
        for table in TABLES:
            for r in payload["tables"][table]:
                expected = {v[1] for v in stage.execute(f"PRAGMA table_info({table})")}
                if set(r) != expected:
                    raise ValueError("La estructura de la copia no coincide.")
                if table == "company":
                    if r["id"] != 1:
                        raise ValueError("Identificador de empresa no válido.")
                else:
                    try:
                        if str(uuid.UUID(str(r["id"]))) != r["id"]:
                            raise ValueError()
                    except (ValueError, TypeError, AttributeError):
                        raise ValueError(
                            "La copia contiene identificadores no válidos."
                        )
                for key in (
                    "facility_id",
                    "document_id",
                    "factor_id",
                    "consumption_id",
                ):
                    if r.get(key) is not None:
                        try:
                            if str(uuid.UUID(str(r[key]))) != r[key]:
                                raise ValueError()
                        except (ValueError, TypeError, AttributeError):
                            raise ValueError(
                                "La copia contiene referencias no válidas."
                            )
                if table == "documents":
                    r["content"] = base64.b64decode(r["content"], validate=True)
                    if hashlib.sha256(r["content"]).hexdigest() != r["hash"] or not r[
                        "content"
                    ].startswith(b"%PDF-"):
                        raise ValueError("Una factura de la copia no es válida.")
                insert(stage, table, r)
        if not one(stage, "SELECT id FROM company WHERE id=1"):
            raise ValueError("La copia no contiene configuración de empresa.")
        for r in rows(stage, "SELECT * FROM consumptions"):
            number(r["quantity"])
            if not valid_unit(r["category"], r["unit"]):
                raise ValueError("Unidad de actividad no válida en la copia.")
            a = date.fromisoformat(r["start"])
            b = date.fromisoformat(r["end"])
            if a > b or a.year != b.year:
                raise ValueError("La copia contiene periodos inválidos.")
            checked_year(a.year)
        for f in rows(stage, "SELECT * FROM factors"):
            number(f["value"])
            country(f["country"])
            if not valid_unit(f["category"], f["unit"], factor=True):
                raise ValueError("Unidad de factor no válida en la copia.")
            if (
                urlparse(f["source"]).scheme not in ("http", "https")
                or not urlparse(f["source"]).netloc
            ):
                raise ValueError("La copia contiene una fuente de factor no válida.")
        for f in rows(stage, "SELECT * FROM facilities"):
            country(f["country"])
            cats = json.loads(f["categories"])
            if (
                not isinstance(cats, list)
                or not cats
                or any(c not in CAT for c in cats)
            ):
                raise ValueError("La copia contiene categorías inválidas.")
        for calc in rows(stage, "SELECT * FROM calculations"):
            number(calc["normalized_quantity"])
            number(calc["kg_co2e"])
        with LOCK, connect() as db:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            backup_dir = g.ledger_path.parent if app.config["MULTI_TENANT"] else DATA
            (backup_dir / f"antes-restauracion-{stamp}.zip").write_bytes(
                backup_bytes(db)
            )
            for table in reversed(TABLES):
                db.execute(f"DELETE FROM {table}")
            for table in TABLES:
                for r in rows(stage, f"SELECT * FROM {table}"):
                    insert(db, table, r)
            event(
                db,
                "backup",
                "1",
                "restored",
                reason="Restauración solicitada por el usuario",
            )
    except (KeyError, TypeError, sqlite3.Error, InvalidOperation):
        raise ValueError(
            "La copia contiene registros inválidos. Los datos actuales se conservan."
        )
    finally:
        stage.close()
    return jsonify(ok=True)


def seed_demo():
    path = DATA / "demo.sqlite"
    initialize(path)
    with connect(path) as db:
        if one(db, "SELECT id FROM facilities"):
            return
        db.execute(
            "UPDATE company SET name=?,country=?,boundary=?,exclusions=? WHERE id=1",
            (
                "Taller del Norte · ejemplo",
                "ES",
                "Ejemplo ficticio: oficina y taller.",
                "Ejemplo parcial; no incluye compras, transporte ni otras fuentes.",
            ),
        )
        fids = []
        for name, cats in [
            ("Oficina central", ["electricity"]),
            ("Taller y almacén", ["electricity", "diesel"]),
        ]:
            fid = uid()
            fids.append(fid)
            insert(
                db,
                "facilities",
                dict(
                    id=fid,
                    name=name,
                    country="ES",
                    ownership="rented",
                    categories=dumps(cats),
                    archived=0,
                    created_at=now(),
                    updated_at=now(),
                ),
            )
        for cat, val, unit in [("electricity", "0.18", "kWh"), ("diesel", "2.4", "L")]:
            insert(
                db,
                "factors",
                dict(
                    id=uid(),
                    name="Factor ficticio de demostración",
                    category=cat,
                    country="ES",
                    year=2026,
                    unit=unit,
                    value=val,
                    source="https://example.invalid/datos-ficticios",
                    version="DEMO-1",
                    license="Solo ejemplo; no válido para cálculo real",
                    validated=1,
                    method="location",
                    created_at=now(),
                    updated_at=now(),
                ),
            )
        for m in range(1, 10):
            for i, fid in enumerate(fids):
                for cat in ["electricity"] if i == 0 else ["electricity", "diesel"]:
                    q = (
                        (700 + i * 900 + (m % 4) * 110)
                        if cat == "electricity"
                        else 100 + m * 8
                    )
                    save_record(
                        db,
                        dict(
                            facility_id=fid,
                            category=cat,
                            quantity=str(q),
                            unit="kWh" if cat == "electricity" else "L",
                            start=f"2026-{m:02d}-01",
                            end=f"2026-{m:02d}-{calendar.monthrange(2026,m)[1]}",
                            reference=f"DEMO-{i}-{cat}-{m}",
                            note="Dato ficticio de demostración",
                        ),
                    )


from algyre_core.accounts import Accounts

accounts = Accounts(app, lambda: DATA, initialize, LOCK)
if MULTI:
    accounts.configure()
else:
    initialize(local_database(DATA))
    seed_demo()
if __name__ == "__main__":
    port = int(os.environ.get("ALGYRE_PORT", "8765"))
    print(f"ALgyre disponible en http://127.0.0.1:{port}", flush=True)
    from waitress import serve

    proxy = (
        dict(
            trusted_proxy="127.0.0.1",
            trusted_proxy_count=1,
            trusted_proxy_headers={"x-forwarded-for", "x-forwarded-proto"},
            clear_untrusted_proxy_headers=True,
        )
        if MULTI
        else {}
    )
    serve(
        app,
        host="127.0.0.1",
        port=port,
        threads=4,
        max_request_body_size=24 * 1024 * 1024,
        **proxy,
    )
