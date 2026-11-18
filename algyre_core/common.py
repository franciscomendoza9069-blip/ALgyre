"""Shared value validation, identifiers and small SQL helpers."""

import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


def dumps(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


def rows(db, sql, args=()):
    return [dict(x) for x in db.execute(sql, args).fetchall()]


def one(db, sql, args=()):
    r = db.execute(sql, args).fetchone()
    return dict(r) if r else None


def event(db, entity, rid, action, before=None, after=None, reason=""):
    db.execute(
        "INSERT INTO events VALUES(?,?,?,?,?,?,?,?)",
        (uid(), entity, rid, action, dumps(before), dumps(after), reason, now()),
    )


def insert(db, table, data):
    cols = list(data)
    db.execute(
        f'INSERT INTO {table} ({",".join(cols)}) VALUES ({",".join("?" for _ in cols)})',
        list(data.values()),
    )


def text(x, maxlen=500):
    s = str(x or "").strip()
    if len(s) > maxlen:
        raise ValueError(f"El texto supera {maxlen} caracteres.")
    return s


def number(x):
    s = str(x).strip().replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        n = Decimal(s)
    except InvalidOperation:
        raise ValueError("Introduce una cantidad numérica válida.")
    if not n.is_finite() or n < 0 or n > Decimal("1e14"):
        raise ValueError("La cantidad debe ser finita y no negativa.")
    return n


def checked_year(x):
    y = int(x)
    if not 2000 <= y <= 2100:
        raise ValueError("El año debe estar entre 2000 y 2100.")
    return y


def country(x):
    c = text(x, 2).upper()
    if not re.fullmatch("[A-Z]{2}", c):
        raise ValueError("Usa un país ISO de dos letras, por ejemplo ES.")
    return c
