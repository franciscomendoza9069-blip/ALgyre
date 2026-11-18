"""Multi-company access boundaries, credential lifecycle and public deployment guards."""

import base64
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import test_app

algyre = test_app.algyre
URL = "https://algyre.example.test"


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = test_app.TestDirectory(
            prefix="qa-accounts-", dir=algyre.ROOT / "work"
        )
        self.old_data = algyre.DATA
        self.old_config = dict(algyre.app.config)
        self.old_url = algyre.accounts.public_url
        algyre.DATA = Path(self.tmp.name)
        algyre.app.config.update(
            TESTING=True,
            MULTI_TENANT=True,
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_SAMESITE="Lax",
        )
        algyre.accounts.public_url = URL
        algyre.accounts.initialize()
        self.mail = []
        algyre.accounts.mailer = lambda address, link, purpose: self.mail.append(
            (address, link.split("=")[1], purpose)
        )
        algyre.accounts.create_admin("admin@example.test", "admin-fixture-password")
        self.a = algyre.accounts.create_company(
            "Empresa A", "a@example.test", "company-a-password", verified=True
        )
        self.b = algyre.accounts.create_company(
            "Empresa B", "b@example.test", "company-b-password", verified=True
        )
        self.ca, self.cb, self.admin = [algyre.app.test_client() for _ in range(3)]
        self.login(self.ca, "a@example.test", "company-a-password")
        self.login(self.cb, "b@example.test", "company-b-password")
        self.login(self.admin, "admin@example.test", "admin-fixture-password")
        algyre.IMPORTS.clear()
        algyre.UPLOADS.clear()

    def tearDown(self):
        algyre.DATA = self.old_data
        algyre.app.config.clear()
        algyre.app.config.update(self.old_config)
        algyre.accounts.public_url = self.old_url
        algyre.accounts.mailer = None
        self.tmp.cleanup()

    def get(self, c, path, **kw):
        return c.get("/api/" + path, base_url=URL, **kw)

    def post(self, c, path, data, **kw):
        token = self.get(c, "status").json["csrf"]
        return c.post(
            "/api/" + path,
            json=data,
            base_url=URL,
            headers={"X-CSRF-Token": token},
            **kw,
        )

    def login(self, c, address, pw):
        r = self.post(c, "login", dict(email=address, password=pw))
        self.assertEqual(r.status_code, 200, r.data)
        return r

    def facility(self, c):
        r = self.post(
            c,
            "facilities",
            dict(
                name="La misma instalación",
                country="ES",
                ownership="owned",
                categories=["electricity"],
            ),
        )
        self.assertEqual(r.status_code, 200, r.data)
        return r.json["id"]

    def record(self, c, fid, **kw):
        data = dict(
            facility_id=fid,
            category="electricity",
            quantity="10",
            unit="kWh",
            start="2026-01-01",
            end="2026-01-31",
            reviewed=True,
        )
        return self.post(c, "consumptions", dict(data, **kw))

    def test_same_names_separate_databases(self):
        fa, fb = self.facility(self.ca), self.facility(self.cb)
        self.assertNotEqual(fa, fb)
        self.assertEqual(self.get(self.ca, "state").json["facilities"][0]["id"], fa)
        self.assertEqual(self.get(self.cb, "state").json["facilities"][0]["id"], fb)
        self.assertNotEqual(
            algyre.accounts.ledger_path(self.a["org_id"]),
            algyre.accounts.ledger_path(self.b["org_id"]),
        )

    def test_foreign_facility_and_record_cannot_be_read_or_written(self):
        fa = self.facility(self.ca)
        self.assertEqual(self.record(self.cb, fa).status_code, 400)
        rid = self.record(self.ca, fa).json["id"]
        self.assertEqual(
            self.get(self.cb, "consumptions/" + rid + "/history").status_code, 404
        )
        self.assertEqual(
            self.post(
                self.cb,
                "facilities/" + fa,
                dict(name="changed", country="ES", categories=["electricity"]),
            ).status_code,
            400,
        )
        self.assertNotIn("La misma instalación", self.get(self.cb, "export.csv").text)

    def test_foreign_documents_and_reports_cannot_be_downloaded(self):
        buf = io.BytesIO()
        pdf = test_app.canvas.Canvas(buf)
        pdf.drawString(10, 10, "Private")
        pdf.save()
        doc = self.post(
            self.ca,
            "documents",
            dict(name="privado.pdf", content=base64.b64encode(buf.getvalue()).decode()),
        ).json["id"]
        report = self.post(self.ca, "reports", {"year": 2026}).json["id"]
        for path in ["documents/" + doc + "/file", "reports/" + report + "/pdf"]:
            self.assertEqual(self.get(self.ca, path).status_code, 200)
            self.assertEqual(self.get(self.cb, path).status_code, 404)

    def test_client_org_parameter_does_not_select_ledger(self):
        self.facility(self.ca)
        self.assertEqual(
            self.get(self.cb, "state?org_id=" + self.a["org_id"]).json["facilities"], []
        )
        with self.cb.session_transaction(base_url=URL) as s:
            s["selected_org"] = self.a["org_id"]
        self.assertEqual(self.get(self.cb, "state").json["facilities"], [])

    def test_anonymous_api_denied_and_old_auth_bypasses_disabled(self):
        c = algyre.app.test_client()
        for path in [
            "state",
            "export.csv",
            "backup",
            "admin/organizations",
            "account",
            "documents/unknown/file",
        ]:
            self.assertEqual(self.get(c, path).status_code, 401, path)
        self.assertEqual(
            self.post(c, "setup", {"password": "random-password"}).status_code, 401
        )
        self.assertEqual(self.post(c, "demo", {}).status_code, 401)
        self.assertEqual(self.post(self.ca, "demo", {}).status_code, 403)

    def test_login_csrf_origin_and_https_required(self):
        c = algyre.app.test_client()
        self.get(c, "status")
        self.assertEqual(
            c.post(
                "/api/login",
                json={"email": "a@example.test", "password": "company-a-password"},
                base_url=URL,
            ).status_code,
            403,
        )
        csrf = self.get(c, "status").json["csrf"]
        self.assertEqual(
            c.post(
                "/api/login",
                json={},
                base_url=URL,
                headers={"X-CSRF-Token": csrf, "Origin": "https://evil.test"},
            ).status_code,
            403,
        )
        self.assertEqual(
            c.get("/api/status", base_url="http://algyre.example.test").status_code, 403
        )
        self.assertEqual(
            c.get("/api/status", base_url="https://evil.test").status_code, 403
        )

    def test_session_cookie_secure_httponly_and_expiry(self):
        r = self.login(self.ca, "a@example.test", "company-a-password")
        cookie = r.headers.get("Set-Cookie", "")
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        with algyre.accounts.db() as db:
            db.execute(
                "UPDATE sessions SET expires=0 WHERE account_id=?", (self.a["id"],)
            )
        self.assertEqual(self.get(self.ca, "state").status_code, 401)

    def test_company_cannot_use_any_admin_action(self):
        self.assertEqual(self.get(self.ca, "admin/organizations").status_code, 403)
        for suffix in ["open", "status", "password", "delete"]:
            self.assertEqual(
                self.post(
                    self.ca,
                    "admin/organizations/" + self.b["org_id"] + "/" + suffix,
                    {"active": False, "password": "another-password"},
                ).status_code,
                403,
            )
        self.assertEqual(self.post(self.ca, "admin/organizations", {}).status_code, 403)

    def test_admin_selects_company_and_switch_invalidates_import_tokens(self):
        self.assertEqual(self.get(self.admin, "state").status_code, 403)
        self.post(self.admin, "admin/organizations/" + self.a["org_id"] + "/open", {})
        self.assertEqual(
            self.get(self.admin, "state").json["company"]["name"], "Empresa A"
        )
        self.facility(self.admin)
        token = self.post(
            self.admin,
            "import/preview",
            {
                "text": "instalacion;categoria;cantidad;unidad;inicio;fin\nLa misma instalación;electricity;10;kWh;2026-01-01;2026-01-31"
            },
        ).json["token"]
        self.post(self.admin, "admin/organizations/" + self.b["org_id"] + "/open", {})
        self.assertEqual(
            self.post(
                self.admin, "import/confirm", dict(token=token, reviewed=True)
            ).status_code,
            400,
        )
        self.assertEqual(self.get(self.admin, "state").json["facilities"], [])

    def test_suspend_revokes_session_and_blocks_login(self):
        self.assertEqual(
            self.post(
                self.admin,
                "admin/organizations/" + self.a["org_id"] + "/status",
                {"active": False},
            ).status_code,
            200,
        )
        self.assertEqual(self.get(self.ca, "state").status_code, 401)
        self.assertEqual(
            self.post(
                self.ca,
                "login",
                dict(email="a@example.test", password="company-a-password"),
            ).status_code,
            401,
        )
        self.assertEqual(self.get(self.cb, "state").status_code, 200)

    def test_admin_password_reset_revokes_other_sessions(self):
        self.post(
            self.admin,
            "admin/organizations/" + self.a["org_id"] + "/password",
            {"password": "new-company-a-password"},
        )
        self.assertEqual(self.get(self.ca, "state").status_code, 401)
        self.login(self.ca, "a@example.test", "new-company-a-password")

    def test_registration_confirmation_one_time_and_no_admin_escalation(self):
        c = algyre.app.test_client()
        r = self.post(
            c,
            "register",
            dict(
                company="Empresa C",
                email="c@example.test",
                password="company-c-password",
                role="admin",
            ),
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            self.post(
                c, "login", dict(email="c@example.test", password="company-c-password")
            ).status_code,
            403,
        )
        token = self.mail[-1][1]
        self.assertEqual(self.post(c, "verify", {"token": token}).status_code, 200)
        self.assertEqual(self.post(c, "verify", {"token": token}).status_code, 400)
        self.login(c, "c@example.test", "company-c-password")
        self.assertEqual(self.get(c, "status").json["role"], "company")
        self.assertEqual(self.get(c, "state").json["records"], [])

    def test_reset_token_one_time_expiring_and_sessions_revoked(self):
        c = algyre.app.test_client()
        self.post(c, "forgot-password", {"email": "a@example.test"})
        token = self.mail[-1][1]
        self.assertEqual(
            self.post(
                c,
                "reset-password",
                dict(token=token, password="reset-company-password"),
            ).status_code,
            200,
        )
        self.assertEqual(self.get(self.ca, "state").status_code, 401)
        self.assertEqual(
            self.post(
                c, "reset-password", dict(token=token, password="another-password")
            ).status_code,
            400,
        )
        self.login(c, "a@example.test", "reset-company-password")
        self.post(c, "forgot-password", {"email": "a@example.test"})
        token = self.mail[-1][1]
        with algyre.accounts.db() as db:
            db.execute("UPDATE tokens SET expires=0")
        self.assertEqual(
            self.post(
                c, "reset-password", dict(token=token, password="another-password")
            ).status_code,
            400,
        )

    def test_logout_and_change_password_close_sessions(self):
        c = algyre.app.test_client()
        self.login(c, "a@example.test", "company-a-password")
        self.assertEqual(
            self.post(
                self.ca,
                "account/password",
                dict(current="company-a-password", password="changed-company-password"),
            ).status_code,
            200,
        )
        self.assertEqual(self.get(c, "state").status_code, 401)
        self.login(c, "a@example.test", "changed-company-password")
        self.post(c, "logout", {})
        self.assertEqual(self.get(c, "state").status_code, 401)

    def test_delete_removes_ledger_account_and_restore_copies(self):
        path = algyre.accounts.ledger_path(self.a["org_id"])
        (path.parent / "antes-restauracion-test.zip").write_bytes(b"private")
        self.assertEqual(
            self.post(
                self.ca,
                "account/delete",
                dict(password="wrong", confirmation="ELIMINAR"),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                self.ca,
                "account/delete",
                dict(password="company-a-password", confirmation="ELIMINAR"),
            ).status_code,
            200,
        )
        self.assertFalse(path.parent.exists())
        with algyre.accounts.db() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT * FROM accounts WHERE id=?", (self.a["id"],)
                ).fetchone()
            )
        self.assertEqual(self.get(self.cb, "state").status_code, 200)

    def test_backup_and_restore_remain_in_current_company(self):
        self.facility(self.ca)
        raw = self.get(self.ca, "backup").data
        result = self.post(
            self.ca,
            "restore",
            dict(content=base64.b64encode(raw).decode(), confirmation="RESTAURAR"),
        )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(self.get(self.cb, "state").json["facilities"], [])
        self.assertTrue(
            list(
                algyre.accounts.ledger_path(self.a["org_id"]).parent.glob(
                    "antes-restauracion-*.zip"
                )
            )
        )
        self.assertFalse(list(algyre.DATA.glob("antes-restauracion-*.zip")))
        self.login(self.ca, "a@example.test", "company-a-password")

    def test_legacy_copy_preserves_records_and_original(self):
        path = algyre.DATA / "old.sqlite"
        algyre.initialize(path)
        with algyre.connect(path) as db:
            db.execute("UPDATE company SET name='Legacy' WHERE id=1")
        before = path.read_bytes()
        account = algyre.accounts.create_company(
            "Legacy",
            "legacy@example.test",
            "legacy-account-password",
            verified=True,
            legacy=path,
        )
        self.assertEqual(path.read_bytes(), before)
        with algyre.connect(algyre.accounts.ledger_path(account["org_id"])) as db:
            self.assertEqual(
                db.execute("SELECT name FROM company").fetchone()[0], "Legacy"
            )

    def test_restore_rejects_markup_in_identifiers_before_admin_can_view_it(self):
        self.facility(self.ca)
        with zipfile.ZipFile(io.BytesIO(self.get(self.ca, "backup").data)) as z:
            payload = json.loads(z.read("algyre.json"))
        payload["tables"]["facilities"][0]["id"] = '" onmouseover="alert(1)'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("algyre.json", json.dumps(payload))
        r = self.post(
            self.ca,
            "restore",
            dict(
                content=base64.b64encode(buf.getvalue()).decode(),
                confirmation="RESTAURAR",
            ),
        )
        self.assertEqual(r.status_code, 400, r.data)
        self.assertNotIn("onmouseover", self.get(self.ca, "state").text)

    def test_login_rate_limit_persists(self):
        c = algyre.app.test_client()
        for _ in range(8):
            self.post(c, "login", dict(email="missing@example.test", password="wrong"))
        self.assertEqual(
            self.post(
                c, "login", dict(email="missing@example.test", password="wrong")
            ).status_code,
            429,
        )

    def test_single_admin_and_registration_pending_without_mail(self):
        import sqlite3

        with self.assertRaises(sqlite3.IntegrityError):
            algyre.accounts.create_admin("other@example.test", "another-admin-password")
        algyre.accounts.mailer = None
        self.assertTrue(self.get(self.ca, "status").json["registration"])
        c = algyre.app.test_client()
        self.assertEqual(
            self.post(
                c,
                "register",
                dict(
                    company="C", email="c@example.test", password="company-c-password"
                ),
            ).status_code,
            200,
        )
        self.assertEqual(
            self.post(
                c, "login", dict(email="c@example.test", password="company-c-password")
            ).status_code,
            403,
        )
        with algyre.accounts.db() as db:
            org = db.execute(
                "SELECT org_id FROM accounts WHERE email=?", ("c@example.test",)
            ).fetchone()[0]
        self.assertEqual(
            self.post(
                self.admin, "admin/organizations/" + org + "/approve", {}
            ).status_code,
            200,
        )
        self.login(c, "c@example.test", "company-c-password")

    def test_bootstrap_requires_secret_and_only_one_admin(self):
        import secrets
        from tenancy import digest, stamp

        c = algyre.app.test_client()
        token = secrets.token_urlsafe(32)
        with algyre.accounts.db() as db:
            db.execute("DELETE FROM accounts WHERE role='admin'")
            db.execute(
                "INSERT INTO installation VALUES(1,?,?)", (digest(token), stamp() + 300)
            )
        data = dict(
            token="wrong",
            email="owner@example.test",
            password="new-admin-password",
            operator_name="Operador QA",
            operator_email="contact@example.test",
        )
        self.assertEqual(self.post(c, "bootstrap", data).status_code, 403)
        data["token"] = token
        self.assertEqual(self.post(c, "bootstrap", data).status_code, 200)
        self.assertEqual(self.get(c, "status").json["role"], "admin")
        self.assertEqual(self.post(c, "bootstrap", data).status_code, 403)
        with algyre.accounts.db() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM installation").fetchone()[0], 0
            )


if __name__ == "__main__":
    unittest.main()
