"""Offline administration. Passwords are prompted, never passed on the command line."""

import argparse
import getpass
import os
from algyre_core.compatibility import load_legacy_environment

load_legacy_environment()
import sqlite3
from pathlib import Path


def secret():
    first = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    if first != getpass.getpass("Repite la contraseña: "):
        raise ValueError("Las contraseñas no coinciden.")
    return first


def main():
    parser = argparse.ArgumentParser(
        description="Administración de ALgyre desde el servidor"
    )
    parser.add_argument(
        "command",
        choices=[
            "migrate",
            "bootstrap-admin",
            "prepare-admin",
            "reset-admin",
            "import-legacy",
            "check",
        ],
    )
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if os.environ.get("ALGYRE_MODE") != "public":
        raise ValueError("Carga primero la configuración pública de ALgyre.")
    import app
    from algyre_core.accounts import email, password
    from werkzeug.security import generate_password_hash

    service = app.accounts
    service.initialize()
    if args.command == "migrate":
        print(
            "Bases de cuentas y actividades actualizadas. Los datos anteriores se conservan."
        )
    elif args.command == "prepare-admin":
        import secrets
        from algyre_core.accounts import digest, stamp

        token = secrets.token_urlsafe(32)
        with service.db() as db:
            if db.execute("SELECT 1 FROM accounts WHERE role='admin'").fetchone():
                raise ValueError("Ya existe un administrador.")
            db.execute(
                "INSERT OR REPLACE INTO installation VALUES(1,?,?)",
                (digest(token), stamp() + 3600),
            )
        print(service.public_url + "/#setup=" + token)
    elif args.command == "bootstrap-admin":
        with service.db() as db:
            if db.execute("SELECT 1 FROM accounts WHERE role='admin'").fetchone():
                raise ValueError(
                    "Ya existe un administrador. Usa reset-admin para recuperar su acceso."
                )
        address = input("Tu correo de administrador: ")
        service.create_admin(address, secret())
        print(
            "Administrador creado. No se ha enviado ningún correo ni mostrado la contraseña."
        )
    elif args.command == "reset-admin":
        address = email(input("Nuevo correo de administrador: "))
        hashed = generate_password_hash(password(secret()))
        with service.db() as db:
            admin = db.execute("SELECT id FROM accounts WHERE role='admin'").fetchone()
            if not admin:
                raise ValueError("Primero crea el administrador.")
            db.execute(
                "UPDATE accounts SET email=?,password=? WHERE id=?",
                (address, hashed, admin["id"]),
            )
            db.execute("DELETE FROM sessions WHERE account_id=?", (admin["id"],))
            db.execute("DELETE FROM tokens WHERE account_id=?", (admin["id"],))
        print("Acceso de administrador actualizado; sesiones anteriores cerradas.")
    elif args.command == "import-legacy":
        if not args.source or not args.source.is_file():
            raise ValueError("Indica --source con la base algyre.sqlite anterior.")
        # Require a real old ledger before copying it. No filename is accepted from a web request.
        with sqlite3.connect(
            f"{args.source.resolve().as_uri()}?mode=ro", uri=True
        ) as db:
            company = db.execute("SELECT name FROM company WHERE id=1").fetchone()
            if not company:
                raise ValueError("La base anterior no contiene una empresa.")
        print(
            "Se copiará la empresa anterior sin modificar el archivo original:",
            company[0],
        )
        account = service.create_company(
            company[0],
            input("Correo para esa empresa: "),
            secret(),
            verified=True,
            legacy=args.source,
        )
        print("Empresa importada:", account["org_id"])
    else:
        with service.db() as db:
            admin = db.execute(
                "SELECT count(*) FROM accounts WHERE role='admin'"
            ).fetchone()[0]
            orgs = db.execute("SELECT id FROM organizations").fetchall()
            missing = [
                o["id"] for o in orgs if not service.ledger_path(o["id"]).is_file()
            ]
        if admin != 1 or missing:
            raise ValueError("Falta el administrador o alguna base de empresa.")
        print(f"Configuración correcta: un administrador y {len(orgs)} empresas.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, sqlite3.Error, RuntimeError) as exc:
        raise SystemExit(str(exc))
