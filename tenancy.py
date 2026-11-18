"""Company accounts and isolated ledgers. No ledger filename comes from a client."""

import hashlib
import hmac
import os
import re
import secrets
import shutil
import smtplib
import sqlite3
import ssl
import time
import uuid
from html import escape
from contextlib import contextmanager
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import HTTPException

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS organizations(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
 created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS accounts(
 id TEXT PRIMARY KEY, org_id TEXT UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
 email TEXT NOT NULL COLLATE NOCASE UNIQUE, password TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('company','admin')), verified INTEGER NOT NULL DEFAULT 0,
 created_at INTEGER NOT NULL, CHECK((role='admin' AND org_id IS NULL) OR (role='company' AND org_id IS NOT NULL)));
CREATE UNIQUE INDEX IF NOT EXISTS one_admin ON accounts(role) WHERE role='admin';
CREATE TABLE IF NOT EXISTS sessions(
 token TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS tokens(
 token TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 purpose TEXT NOT NULL, expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS installation(id INTEGER PRIMARY KEY CHECK(id=1), token TEXT NOT NULL, expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
PRAGMA user_version=1;
"""


def stamp():
    return int(time.time())


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def email(value):
    value = str(value or "").strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value):
        raise ValueError("Introduce un correo electrónico válido.")
    return value


def password(value):
    if not isinstance(value, str) or not 12 <= len(value) <= 200:
        raise ValueError("La contraseña debe tener entre 12 y 200 caracteres.")
    return value


def body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError("Se esperaba un objeto JSON.")
    return value


class Accounts:
    def __init__(self, app, data_dir, initialize_ledger, lock):
        self.app, self.data_dir, self.initialize_ledger, self.lock = (
            app,
            data_dir,
            initialize_ledger,
            lock,
        )
        self.public_url = os.environ.get("ALGYRE_PUBLIC_URL", "").rstrip("/")
        self.mailer = None  # Tests inject a mailbox; production always uses SMTP.
        self.dummy_hash = generate_password_hash(secrets.token_hex(24))
        self.routes()

    @property
    def root(self):
        return Path(self.data_dir())

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.root / "accounts.sqlite", timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "tenants").mkdir(exist_ok=True)
        with self.db() as db:
            db.executescript(SCHEMA)

    def configure(self):
        parsed = urlsplit(self.public_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise RuntimeError(
                "ALGYRE_PUBLIC_URL debe ser el origen HTTPS público, por ejemplo https://203.0.113.10"
            )
        self.initialize()
        key = os.environ.get("ALGYRE_SECRET_KEY", "")
        if len(key) < 32:
            raise RuntimeError(
                "Configura ALGYRE_SECRET_KEY con al menos 32 caracteres aleatorios."
            )
        self.app.config.update(
            SECRET_KEY=key,
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            SESSION_COOKIE_NAME="algyre_session",
            PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        )
        with self.db() as identity:
            organizations = identity.execute("SELECT id FROM organizations").fetchall()
        for organization in organizations:
            path = self.ledger_path(organization["id"])
            if not path.is_file():
                raise RuntimeError(
                    "Falta la base de una empresa. Revisa las copias antes de continuar."
                )
            self.initialize_ledger(path)
        # Waitress trusts forwarded scheme/client headers only from loopback Apache.

    def ledger_path(self, org_id):
        # Only canonical UUIDs generated by this service can select a directory.
        if str(uuid.UUID(org_id)) != org_id:
            raise ValueError("Empresa no válida.")
        return self.root / "tenants" / org_id / "ledger.sqlite"

    def csrf(self):
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(24)
        return session["csrf"]

    def guard(self):
        if request.host_url.rstrip("/") != self.public_url or not request.is_secure:
            return (
                jsonify(
                    error="Accede mediante la dirección HTTPS configurada de ALgyre."
                ),
                403,
            )
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("Origin")
            if origin and origin != self.public_url:
                return jsonify(error="Origen no permitido."), 403
            if request.path.startswith("/api/") and not hmac.compare_digest(
                request.headers.get("X-CSRF-Token", ""), self.csrf()
            ):
                return jsonify(error="Recarga la página y vuelve a intentarlo."), 403
        account = None
        if session.get("auth_token"):
            with self.db() as db:
                account = db.execute(
                    "SELECT a.* FROM sessions s JOIN accounts a ON a.id=s.account_id "
                    "WHERE s.token=? AND s.expires>?",
                    (digest(session["auth_token"]), stamp()),
                ).fetchone()
        if account:
            g.account = dict(account)
            org_id = (
                account["org_id"]
                if account["role"] == "company"
                else session.get("selected_org")
            )
            if org_id:
                with self.db() as db:
                    org = db.execute(
                        "SELECT * FROM organizations WHERE id=? AND active=1", (org_id,)
                    ).fetchone()
                if not org:
                    if account["role"] == "company":
                        session.clear()
                        return (
                            jsonify(error="La cuenta de empresa está desactivada."),
                            401,
                        )
                    session.pop("selected_org", None)
                else:
                    g.organization = dict(org)
                    g.ledger_path = self.ledger_path(org["id"])
        elif session.get("auth_token"):
            session.clear()
        public = {
            "/api/status",
            "/api/login",
            "/api/register",
            "/api/verify",
            "/api/forgot-password",
            "/api/reset-password",
            "/api/health",
            "/api/bootstrap",
        }
        if request.path.startswith("/api/") and request.path not in public:
            if not account:
                return jsonify(error="Inicia sesión para continuar."), 401
            if request.path.startswith("/api/admin/") and account["role"] != "admin":
                return (
                    jsonify(error="Solo el administrador puede realizar esta acción."),
                    403,
                )
            if request.path not in {
                "/api/logout",
                "/api/account",
                "/api/account/password",
                "/api/account/delete",
            } and not request.path.startswith("/api/admin/"):
                if not getattr(g, "ledger_path", None):
                    return (
                        jsonify(error="Selecciona una empresa desde Administración."),
                        403,
                    )

    def throttle(self, action, identifier="", count=8, seconds=900):
        # Persistent buckets survive worker/server restarts; no email or IP is kept in clear text.
        key = digest(f"{action}:{identifier or request.remote_addr}:{stamp()//seconds}")
        with self.lock, self.db() as db:
            db.execute("DELETE FROM limits WHERE expires<?", (stamp(),))
            db.execute(
                "INSERT INTO limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1",
                (key, stamp() + seconds),
            )
            n = db.execute("SELECT count FROM limits WHERE key=?", (key,)).fetchone()[0]
        if n > count:
            abort(429, description="Demasiados intentos. Espera unos minutos.")

    def status(self):
        account = getattr(g, "account", None)
        with self.db() as db:
            configured = bool(
                db.execute("SELECT 1 FROM accounts WHERE role='admin'").fetchone()
            )
        return jsonify(
            multi=True,
            configured=configured,
            authenticated=bool(account),
            demo=False,
            csrf=self.csrf(),
            role=account["role"] if account else None,
            email=account["email"] if account else None,
            organization=getattr(g, "organization", None),
            registration=configured,
            email_confirmation=self.mail_enabled(),
        )

    def begin_session(self, account):
        token = secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute("DELETE FROM sessions WHERE expires<?", (stamp(),))
            db.execute(
                "INSERT INTO sessions VALUES(?,?,?)",
                (digest(token), account["id"], stamp() + 8 * 3600),
            )
        session.clear()
        session.update(
            auth_token=token,
            auth=True,
            demo=False,
            sid=str(uuid.uuid4()),
            csrf=secrets.token_hex(24),
        )
        session.permanent = True
        return jsonify(ok=True, csrf=session["csrf"], role=account["role"])

    def login(self):
        d = body()
        self.throttle("login-ip", count=30, seconds=60)
        address = email(d.get("email"))
        self.throttle("login-email", address, count=8, seconds=300)
        candidate = str(d.get("password", ""))
        with self.db() as db:
            account = db.execute(
                "SELECT * FROM accounts WHERE email=?", (address,)
            ).fetchone()
            active = (
                not account
                or not account["org_id"]
                or bool(
                    db.execute(
                        "SELECT 1 FROM organizations WHERE id=? AND active=1",
                        (account["org_id"],),
                    ).fetchone()
                )
            )
        valid = check_password_hash(
            account["password"] if account else self.dummy_hash, candidate[:201]
        )
        if not account or not valid or len(candidate) > 200 or not active:
            return jsonify(error="Correo o contraseña incorrectos."), 401
        if not account["verified"]:
            return (
                jsonify(
                    error="Cuenta pendiente: confirma tu correo o espera la aprobación del administrador."
                ),
                403,
            )
        return self.begin_session(account)

    def logout(self):
        with self.db() as db:
            db.execute(
                "DELETE FROM sessions WHERE token=?",
                (digest(session.get("auth_token", "")),),
            )
        session.clear()
        return jsonify(ok=True)

    def mail_enabled(self):
        return bool(
            self.mailer
            or (
                os.environ.get("ALGYRE_SMTP_HOST")
                and os.environ.get("ALGYRE_MAIL_FROM")
            )
        )

    def send_link(self, address, token, purpose):
        link = f"{self.public_url}/#{purpose}={token}"
        if self.mailer:
            self.mailer(address, link, purpose)
            return
        message = EmailMessage()
        message["From"] = os.environ["ALGYRE_MAIL_FROM"]
        message["To"] = address
        message["Subject"] = (
            "Confirma tu cuenta de ALgyre"
            if purpose == "verify"
            else "Recupera el acceso a ALgyre"
        )
        message.set_content(
            (
                "Confirma tu correo"
                if purpose == "verify"
                else "Elige una nueva contraseña"
            )
            + f" abriendo este enlace:\n{link}\n\nSi no lo has solicitado, ignora este mensaje."
        )
        host, port = os.environ["ALGYRE_SMTP_HOST"], int(
            os.environ.get("ALGYRE_SMTP_PORT", "587")
        )
        smtp_cls = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        kwargs = {"context": ssl.create_default_context()} if port == 465 else {}
        with smtp_cls(host, port, timeout=15, **kwargs) as smtp:
            if port != 465:
                smtp.starttls(context=ssl.create_default_context())
            if os.environ.get("ALGYRE_SMTP_USER"):
                smtp.login(
                    os.environ["ALGYRE_SMTP_USER"],
                    os.environ.get("ALGYRE_SMTP_PASSWORD", ""),
                )
            smtp.send_message(message)

    def issue_token(self, account_id, purpose):
        token = secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute(
                "DELETE FROM tokens WHERE account_id=? AND purpose=?",
                (account_id, purpose),
            )
            db.execute("DELETE FROM tokens WHERE expires<?", (stamp(),))
            db.execute(
                "INSERT INTO tokens VALUES(?,?,?,?)",
                (
                    digest(token),
                    account_id,
                    purpose,
                    stamp() + (86400 if purpose == "verify" else 1800),
                ),
            )
        return token

    def create_company(self, name, address, pw, verified=False, legacy=None):
        name = str(name or "").strip()
        if not name or len(name) > 160:
            raise ValueError("Introduce un nombre de empresa de hasta 160 caracteres.")
        address, pw = email(address), password(pw)
        org_id, account_id = str(uuid.uuid4()), str(uuid.uuid4())
        path = self.ledger_path(org_id)
        with self.lock:
            path.parent.mkdir(parents=True, exist_ok=False)
            try:
                if legacy:
                    source = sqlite3.connect(
                        f"{Path(legacy).resolve().as_uri()}?mode=ro", uri=True
                    )
                    target = sqlite3.connect(path)
                    try:
                        source.backup(target)
                    finally:
                        target.close()
                        source.close()
                self.initialize_ledger(path)
                ledger = sqlite3.connect(path)
                try:
                    with ledger:
                        ledger.execute("DELETE FROM auth")
                        if not legacy:
                            ledger.execute(
                                "UPDATE company SET name=? WHERE id=1", (name,)
                            )
                finally:
                    ledger.close()
                with self.db() as db:
                    db.execute(
                        "INSERT INTO organizations VALUES(?,?,1,?)",
                        (org_id, name, stamp()),
                    )
                    db.execute(
                        "INSERT INTO accounts VALUES(?,?,?,?,?,?,?)",
                        (
                            account_id,
                            org_id,
                            address,
                            generate_password_hash(pw),
                            "company",
                            int(verified),
                            stamp(),
                        ),
                    )
            except Exception:
                shutil.rmtree(path.parent)
                raise
        return {"id": account_id, "org_id": org_id, "email": address, "role": "company"}

    def create_admin(self, address, pw):
        self.initialize()
        with self.db() as db:
            db.execute(
                "INSERT INTO accounts VALUES(?,NULL,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    email(address),
                    generate_password_hash(password(pw)),
                    "admin",
                    1,
                    stamp(),
                ),
            )

    def require_admin(self):
        if not getattr(g, "account", None) or g.account["role"] != "admin":
            abort(403)

    def delete_company(self, org_id):
        path = self.ledger_path(org_id)
        with self.lock, self.db() as db:
            db.execute("DELETE FROM organizations WHERE id=?", (org_id,))
            if path.parent.exists():
                shutil.rmtree(path.parent)

    def routes(self):
        app = self.app

        @app.errorhandler(HTTPException)
        def http_error(exc):
            return jsonify(error=exc.description), exc.code

        @app.get("/privacy")
        @app.get("/terms")
        def legal_page():
            settings = {}
            if app.config["MULTI_TENANT"]:
                with self.db() as db:
                    settings = {
                        r["key"]: r["value"]
                        for r in db.execute("SELECT * FROM settings")
                    }
            operator = escape(
                settings.get("operator_name")
                or os.environ.get("ALGYRE_OPERATOR_NAME", "Administrador de ALgyre")
            )
            contact = escape(
                settings.get("operator_email")
                or os.environ.get(
                    "ALGYRE_OPERATOR_EMAIL", "Contacta con quien te facilitó el acceso."
                )
            )
            if request.path == "/privacy":
                title = "Privacidad de ALgyre"
                content = f"<p>Responsable del servicio: {operator}. Contacto: {contact}.</p><p>Guardamos el correo de acceso, la contraseña protegida mediante un resumen criptográfico y los datos y documentos que tu empresa incorpora. Se utilizan para proporcionar acceso y gestionar sus consumos e informes.</p><p>Los datos se alojan en el servidor del responsable. Si se configura correo, su proveedor procesa la dirección y los mensajes de confirmación o recuperación. No enviamos facturas a servicios de inteligencia artificial ni incorporamos publicidad o analítica externa.</p><p>Utilizamos una cookie necesaria para mantener la sesión. El servidor guarda registros de errores y conexiones para su funcionamiento y protección.</p><p>Puedes exportar los datos o eliminar la cuenta de empresa desde Configuración. La eliminación borra los datos activos; las copias generales de seguridad caducan en 14 días si se usa la configuración de despliegue incluida. Para consultas y solicitudes, utiliza el contacto indicado.</p>"
            else:
                title = "Condiciones de uso de ALgyre"
                content = f"<p>Servicio administrado por {operator}. Contacto: {contact}.</p><p>Cada empresa dispone de una cuenta compartida para sus personas autorizadas. La empresa debe proteger sus credenciales, revisar quién las conoce y cambiarlas cuando sea necesario. El administrador general puede gestionar cuentas y acceder a los espacios para dar soporte.</p><p>Sube únicamente documentos que tengas autorización para utilizar. Eres responsable de revisar cantidades, periodos, factores de emisión y sus fuentes antes de utilizar o comunicar los resultados.</p><p>Los cálculos e informes incluyen las fuentes incorporadas. Son herramientas de trabajo internas y no constituyen una certificación ni una verificación externa de la huella completa.</p><p>El servicio puede detenerse para mantenimiento. Conserva también tus propias exportaciones. Puedes eliminar la cuenta y sus datos desde Configuración.</p>"
            return f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · ALgyre</title><link rel="stylesheet" href="/static/tokens.css"><link rel="stylesheet" href="/static/style.css"><main class="content"><h1>{title}</h1>{content}<p><a href="/">Volver a ALgyre</a></p></main></html>'

        @app.errorhandler(429)
        def limited(exc):
            return jsonify(error=exc.description), 429, {"Retry-After": "300"}

        @app.get("/api/health")
        def account_health():
            if not app.config["MULTI_TENANT"]:
                return jsonify(ok=True)
            with self.db() as db:
                db.execute("SELECT 1").fetchone()
            return jsonify(ok=True)

        @app.post("/api/bootstrap")
        def bootstrap_admin():
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.throttle("bootstrap", count=5, seconds=900)
            d = body()
            with self.lock, self.db() as db:
                pending = db.execute(
                    "SELECT * FROM installation WHERE id=1 AND expires>?", (stamp(),)
                ).fetchone()
                if (
                    not pending
                    or not hmac.compare_digest(
                        pending["token"], digest(str(d.get("token", "")))
                    )
                    or db.execute(
                        "SELECT 1 FROM accounts WHERE role='admin'"
                    ).fetchone()
                ):
                    return (
                        jsonify(
                            error="El enlace de instalación no es válido o ha caducado."
                        ),
                        403,
                    )
                operator_name = str(d.get("operator_name", "")).strip()
                if not operator_name or len(operator_name) > 160:
                    raise ValueError("Indica el nombre del responsable del servicio.")
                operator_email = email(d.get("operator_email"))
                account = {"id": str(uuid.uuid4()), "role": "admin"}
                db.execute(
                    "INSERT INTO accounts VALUES(?,NULL,?,?,?,?,?)",
                    (
                        account["id"],
                        email(d.get("email")),
                        generate_password_hash(password(d.get("password"))),
                        "admin",
                        1,
                        stamp(),
                    ),
                )
                db.executemany(
                    "INSERT OR REPLACE INTO settings VALUES(?,?)",
                    [
                        ("operator_name", operator_name),
                        ("operator_email", operator_email),
                    ],
                )
                db.execute("DELETE FROM installation")
            return self.begin_session(account)

        @app.post("/api/register")
        def account_register():
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.throttle("register", count=5, seconds=3600)
            with self.db() as db:
                if not db.execute(
                    "SELECT 1 FROM accounts WHERE role='admin'"
                ).fetchone():
                    abort(503)
            d = body()
            try:
                account = self.create_company(
                    d.get("company"), d.get("email"), d.get("password")
                )
            except sqlite3.IntegrityError:
                # Same response for existing addresses, avoiding account enumeration.
                return jsonify(
                    ok=True,
                    message=(
                        "Solicitud registrada. Si el correo está disponible, podrás confirmar el acceso por correo o con el administrador."
                        if self.mail_enabled()
                        else "Solicitud registrada. El administrador debe aprobar tu empresa antes de que puedas entrar."
                    ),
                )
            if not self.mail_enabled():
                return jsonify(
                    ok=True,
                    message="Solicitud registrada. El administrador debe aprobar tu empresa antes de que puedas entrar.",
                )
            token = self.issue_token(account["id"], "verify")
            try:
                self.send_link(account["email"], token, "verify")
            except (OSError, smtplib.SMTPException):
                self.delete_company(account["org_id"])
                return (
                    jsonify(error="No se pudo enviar el correo. Inténtalo más tarde."),
                    503,
                )
            return jsonify(
                ok=True,
                message="Solicitud registrada. Si el correo está disponible, podrás confirmar el acceso por correo o con el administrador.",
            )

        @app.post("/api/verify")
        def account_verify():
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.throttle("verify", count=20, seconds=300)
            token = str(body().get("token", ""))
            with self.lock, self.db() as db:
                row = db.execute(
                    "SELECT * FROM tokens WHERE token=? AND purpose='verify' AND expires>?",
                    (digest(token), stamp()),
                ).fetchone()
                if not row:
                    return jsonify(error="El enlace ha caducado o ya se utilizó."), 400
                db.execute(
                    "UPDATE accounts SET verified=1 WHERE id=?", (row["account_id"],)
                )
                db.execute("DELETE FROM tokens WHERE token=?", (digest(token),))
            return jsonify(ok=True)

        @app.post("/api/forgot-password")
        def account_forgot():
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.throttle("forgot-ip", count=10, seconds=900)
            d = body()
            address = email(d.get("email"))
            self.throttle("forgot-email", address, count=3, seconds=900)
            if not self.mail_enabled():
                return (
                    jsonify(
                        error="Contacta con el administrador para recuperar el acceso."
                    ),
                    503,
                )
            with self.db() as db:
                account = db.execute(
                    "SELECT * FROM accounts WHERE email=?", (address,)
                ).fetchone()
            if account:
                purpose = "reset" if account["verified"] else "verify"
                token = self.issue_token(account["id"], purpose)
                try:
                    self.send_link(address, token, purpose)
                except (OSError, smtplib.SMTPException):
                    return (
                        jsonify(
                            error="No se pudo enviar el correo. Inténtalo más tarde."
                        ),
                        503,
                    )
            return jsonify(
                ok=True,
                message="Si existe una cuenta con ese correo, recibirás un enlace.",
            )

        @app.post("/api/reset-password")
        def account_reset():
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.throttle("reset", count=10, seconds=900)
            d = body()
            new_hash = generate_password_hash(password(d.get("password")))
            with self.lock, self.db() as db:
                row = db.execute(
                    "SELECT * FROM tokens WHERE token=? AND purpose='reset' AND expires>?",
                    (digest(str(d.get("token", ""))), stamp()),
                ).fetchone()
                if not row:
                    return jsonify(error="El enlace ha caducado o ya se utilizó."), 400
                db.execute(
                    "UPDATE accounts SET password=? WHERE id=?",
                    (new_hash, row["account_id"]),
                )
                db.execute(
                    "DELETE FROM sessions WHERE account_id=?", (row["account_id"],)
                )
                db.execute(
                    "DELETE FROM tokens WHERE account_id=?", (row["account_id"],)
                )
            session.clear()
            return jsonify(ok=True)

        @app.get("/api/account")
        def account_info():
            if not app.config["MULTI_TENANT"]:
                abort(404)
            return jsonify(
                email=g.account["email"],
                role=g.account["role"],
                organization=getattr(g, "organization", None),
            )

        @app.post("/api/account/password")
        def account_password():
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.throttle("change-password", g.account["id"], count=5, seconds=900)
            d = body()
            if not check_password_hash(
                g.account["password"], str(d.get("current", ""))[:201]
            ):
                return jsonify(error="Contraseña actual incorrecta."), 403
            with self.db() as db:
                db.execute(
                    "UPDATE accounts SET password=? WHERE id=?",
                    (
                        generate_password_hash(password(d.get("password"))),
                        g.account["id"],
                    ),
                )
                db.execute(
                    "DELETE FROM sessions WHERE account_id=?", (g.account["id"],)
                )
                db.execute("DELETE FROM tokens WHERE account_id=?", (g.account["id"],))
            session.clear()
            return jsonify(ok=True)

        @app.post("/api/account/delete")
        def account_delete():
            if not app.config["MULTI_TENANT"]:
                abort(404)
            d = body()
            self.throttle("delete", g.account["id"], count=5, seconds=900)
            if g.account["role"] == "admin":
                return (
                    jsonify(
                        error="La cuenta de administrador no se puede eliminar aquí."
                    ),
                    403,
                )
            if d.get("confirmation") != "ELIMINAR" or not check_password_hash(
                g.account["password"], str(d.get("password", ""))[:201]
            ):
                return jsonify(error="Confirma con ELIMINAR y tu contraseña."), 403
            self.delete_company(g.account["org_id"])
            session.clear()
            return jsonify(ok=True)

        @app.get("/api/admin/organizations")
        def admin_organizations():
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.require_admin()
            with self.db() as db:
                orgs = [
                    dict(r)
                    for r in db.execute(
                        "SELECT o.*,a.email,a.verified FROM organizations o JOIN accounts a ON a.org_id=o.id ORDER BY o.created_at DESC"
                    )
                ]
            return jsonify(organizations=orgs)

        @app.post("/api/admin/organizations")
        def admin_create():
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.require_admin()
            d = body()
            return jsonify(
                ok=True,
                organization=self.create_company(
                    d.get("company"), d.get("email"), d.get("password"), verified=True
                )["org_id"],
            )

        @app.post("/api/admin/organizations/<org_id>/open")
        def admin_open(org_id):
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.require_admin()
            with self.db() as db:
                org = db.execute(
                    "SELECT * FROM organizations WHERE id=? AND active=1", (org_id,)
                ).fetchone()
            if not org:
                abort(404)
            session.update(
                selected_org=org_id, sid=str(uuid.uuid4()), csrf=secrets.token_hex(24)
            )
            return jsonify(ok=True, csrf=session["csrf"])

        @app.post("/api/admin/organizations/<org_id>/status")
        def admin_toggle(org_id):
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.require_admin()
            d = body()
            if type(d.get("active")) is not bool:
                raise ValueError("Estado no válido.")
            with self.lock, self.db() as db:
                if not db.execute(
                    "SELECT 1 FROM organizations WHERE id=?", (org_id,)
                ).fetchone():
                    abort(404)
                db.execute(
                    "UPDATE organizations SET active=? WHERE id=?",
                    (int(d["active"]), org_id),
                )
                db.execute(
                    "DELETE FROM sessions WHERE account_id IN (SELECT id FROM accounts WHERE org_id=?)",
                    (org_id,),
                )
            return jsonify(ok=True)

        @app.post("/api/admin/organizations/<org_id>/password")
        def admin_password(org_id):
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.require_admin()
            d = body()
            with self.db() as db:
                if not db.execute(
                    "SELECT 1 FROM accounts WHERE org_id=?", (org_id,)
                ).fetchone():
                    abort(404)
                db.execute(
                    "UPDATE accounts SET password=?,verified=1 WHERE org_id=?",
                    (generate_password_hash(password(d.get("password"))), org_id),
                )
                db.execute(
                    "DELETE FROM sessions WHERE account_id IN (SELECT id FROM accounts WHERE org_id=?)",
                    (org_id,),
                )
                db.execute(
                    "DELETE FROM tokens WHERE account_id IN (SELECT id FROM accounts WHERE org_id=?)",
                    (org_id,),
                )
            return jsonify(ok=True)

        @app.post("/api/admin/organizations/<org_id>/approve")
        def admin_approve(org_id):
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.require_admin()
            with self.db() as db:
                if not db.execute(
                    "SELECT 1 FROM accounts WHERE org_id=?", (org_id,)
                ).fetchone():
                    abort(404)
                db.execute("UPDATE accounts SET verified=1 WHERE org_id=?", (org_id,))
            return jsonify(ok=True)

        @app.post("/api/admin/organizations/<org_id>/delete")
        def admin_delete(org_id):
            if not app.config["MULTI_TENANT"]:
                abort(404)
            self.require_admin()
            d = body()
            self.throttle("admin-delete", g.account["id"], count=5, seconds=900)
            if d.get("confirmation") != "ELIMINAR" or not check_password_hash(
                g.account["password"], str(d.get("password", ""))[:201]
            ):
                return (
                    jsonify(
                        error="Confirma con ELIMINAR y tu contraseña de administrador."
                    ),
                    403,
                )
            self.delete_company(org_id)
            return jsonify(ok=True)
