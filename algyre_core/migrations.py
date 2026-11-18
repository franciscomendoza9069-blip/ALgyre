"""Transactional expansion of legacy ledger constraints, with a prior backup."""

import sqlite3
from pathlib import Path


def migrate_ledger(db, path, schema):
    definition = db.execute(
        "SELECT sql FROM sqlite_master WHERE name='factors'"
    ).fetchone()
    if not definition or "refrigerant" in definition[0]:
        return
    # initialize() calls this before writes. Never disable foreign keys in a transaction.
    if db.in_transaction:
        raise RuntimeError("La migración necesita una conexión sin transacción activa.")
    backup = Path(path).with_name("antes-alcance-v2-" + Path(path).name)
    if not backup.exists():
        target = sqlite3.connect(backup)
        try:
            db.backup(target)
        finally:
            target.close()
    statements = [
        statement.strip() for statement in schema.split(";") if statement.strip()
    ]
    db.execute("PRAGMA foreign_keys=OFF")
    try:
        db.execute("BEGIN IMMEDIATE")
        for table in ("factors", "consumptions"):
            create = next(
                s
                for s in statements
                if s.startswith(f"CREATE TABLE IF NOT EXISTS {table}(")
            )
            db.execute(create.replace(f"{table}(", f"{table}_v2(", 1))
            db.execute(f"INSERT INTO {table}_v2 SELECT * FROM {table}")
            db.execute(f"DROP TABLE {table}")
            db.execute(f"ALTER TABLE {table}_v2 RENAME TO {table}")
        for statement in statements:
            if statement.startswith("CREATE INDEX"):
                db.execute(statement)
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError(
                "La migración encontró relaciones inválidas; no se aplicó."
            )
        db.execute("PRAGMA user_version=2")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute("PRAGMA foreign_keys=ON")
