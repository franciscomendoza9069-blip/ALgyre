"""Integration tests on isolated databases; never touch the user's ledger."""

import base64
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import shutil
import uuid
import unittest
import zipfile
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
(ROOT / "work").mkdir(exist_ok=True)


class TestDirectory:
    """Inherit workspace ACLs on Windows instead of Python 3.14's private temp ACL."""

    def __init__(self, prefix="qa-", dir=None):
        self.parent = Path(dir or ROOT / "work").resolve()
        self.path = self.parent / (prefix + uuid.uuid4().hex)
        self.path.mkdir(mode=0o755)
        self.name = str(self.path)

    def cleanup(self):
        if self.path.resolve().parent != self.parent:
            raise RuntimeError("Unsafe test cleanup path")
        if self.path.exists():
            shutil.rmtree(self.path)


BOOT = TestDirectory(prefix="qa-boot-", dir=ROOT / "work")
os.environ["ALGYRE_DATA_DIR"] = BOOT.name
import app as algyre
from reportlab.pdfgen import canvas
from pypdf import PdfReader


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TestDirectory(prefix="qa-", dir=ROOT / "work")
        algyre.DATA = Path(self.tmp.name)
        algyre.initialize(algyre.DATA / "algyre.sqlite")
        algyre.ATTEMPTS.clear()
        algyre.IMPORTS.clear()
        algyre.app.config["TESTING"] = True
        self.c = algyre.app.test_client()
        r = self.c.post("/api/setup", json={"password": "fixture-only-password"})
        self.assertEqual(r.status_code, 200, r.data)
        self.csrf = r.json["csrf"]
        r = self.post(
            "facilities",
            dict(
                name="Instalación QA",
                country="ES",
                ownership="rented",
                categories=["electricity", "diesel"],
            ),
        )
        self.fid = r.json["id"]

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, p, data):
        return self.c.post("/api/" + p, json=data, headers={"X-CSRF-Token": self.csrf})

    def state(self):
        r = self.c.get("/api/state?year=2026")
        self.assertEqual(r.status_code, 200, r.data)
        return r.json

    def record(self, **kw):
        d = dict(
            facility_id=self.fid,
            category="electricity",
            quantity="1000",
            unit="kWh",
            start="2026-01-01",
            end="2026-01-31",
            reference="QA-001",
            reviewed=True,
        )
        d.update(kw)
        return d

    def factor(self, **kw):
        d = dict(
            name="FICTICIO PARA PRUEBA",
            country="ES",
            year=2026,
            category="electricity",
            unit="kWh",
            value="0,2",
            source="https://example.invalid/qa",
            version="QA-1",
            license="Solo pruebas",
            validated=True,
        )
        d.update(kw)
        r = self.post("factors", d)
        self.assertEqual(r.status_code, 200, r.data)
        return r.json["id"]

    def pdf(self):
        buf = io.BytesIO()
        p = canvas.Canvas(buf)
        p.drawString(40, 800, "Factura QA")
        p.drawString(40, 780, "Consumo 1.250,50 kWh")
        p.drawString(40, 760, "Periodo: 01/01/2026 a 31/01/2026")
        p.save()
        return buf.getvalue()

    def test_private_read_csrf_and_origin(self):
        other = algyre.app.test_client()
        for endpoint in (
            "state",
            "backup",
            "export.csv",
            "documents/no/file",
            "reports/no/pdf",
        ):
            self.assertEqual(other.get("/api/" + endpoint).status_code, 401)
        self.assertEqual(self.c.post("/api/company", json={}).status_code, 403)
        self.assertEqual(
            self.c.post(
                "/api/login", json={}, headers={"Origin": "https://evil.example"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.c.get("/api/status", headers={"Host": "evil.example"}).status_code, 403
        )

    def test_setup_once_logout_password(self):
        self.assertEqual(
            self.c.post(
                "/api/setup", json={"password": "another-password"}
            ).status_code,
            409,
        )
        self.post("logout", {})
        self.assertEqual(self.c.get("/api/state").status_code, 401)
        self.assertEqual(
            self.c.post("/api/login", json={"password": "wrong-password"}).status_code,
            401,
        )
        self.assertEqual(
            self.c.post(
                "/api/login", json={"password": "fixture-only-password"}
            ).status_code,
            200,
        )

    def test_login_throttle(self):
        for i in range(5):
            self.assertEqual(
                self.c.post("/api/login", json={"password": "bad"}).status_code, 401
            )
        self.assertEqual(
            self.c.post("/api/login", json={"password": "bad"}).status_code, 429
        )

    def test_no_factor_is_pending_not_zero(self):
        self.assertEqual(self.post("consumptions", self.record()).status_code, 200)
        s = self.state()
        self.assertIsNone(s["records"][0]["kg_co2e"])
        self.assertEqual(s["summary"]["pending"], 1)

    def test_mwh_conversion_decimal_and_coverage(self):
        self.factor()
        r = self.post("consumptions", self.record(quantity="1,25", unit="MWh"))
        self.assertEqual(r.status_code, 200, r.data)
        s = self.state()
        self.assertEqual(Decimal(s["summary"]["total"]), Decimal("250"))
        self.assertEqual(s["summary"]["covered"], 1)
        self.assertEqual(Decimal(s["summary"]["monthly"][0]), Decimal("250"))

    def test_factor_year_country_unit_must_match(self):
        self.factor(year=2025)
        self.factor(country="FR")
        self.factor(category="diesel", unit="L")
        self.post("consumptions", self.record())
        self.assertEqual(self.state()["summary"]["pending"], 1)
        self.factor()
        self.assertEqual(self.state()["summary"]["pending"], 0)

    def test_ambiguous_factor_needs_explicit_selection(self):
        f = self.factor()
        self.factor(version="QA-2")
        self.post("consumptions", self.record())
        self.assertEqual(self.state()["summary"]["pending"], 1)
        r = self.state()["records"][0]
        res = self.post(
            "consumptions/" + r["id"],
            self.record(factor_id=f, revision=1, reason="Seleccionar factor"),
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.state()["summary"]["pending"], 0)

    def test_duplicate_and_overlap(self):
        self.post("consumptions", self.record())
        self.assertEqual(self.post("consumptions", self.record()).status_code, 400)
        self.assertEqual(
            self.post("consumptions", self.record(reference="OTRO")).status_code, 400
        )
        r = self.post(
            "consumptions",
            self.record(reference="OTRO", allow_overlap=True, note="Segundo contador"),
        )
        self.assertEqual(r.status_code, 200, r.data)

    def test_bad_dates_nonfinite_and_crossyear(self):
        for kw in (
            dict(start="2026-02-30"),
            dict(end="2025-12-31"),
            dict(end="2027-01-01"),
            dict(quantity="NaN"),
            dict(quantity="-1"),
            dict(unit="L"),
        ):
            self.assertEqual(
                self.post("consumptions", self.record(**kw)).status_code, 400
            )

    def test_edit_revision_history(self):
        self.factor()
        r = self.post("consumptions", self.record()).json["id"]
        self.assertEqual(
            self.post(
                "consumptions/" + r,
                self.record(quantity="2000", revision=1, reason="Corrección"),
            ).status_code,
            200,
        )
        self.assertEqual(
            self.post(
                "consumptions/" + r,
                self.record(quantity="3000", revision=1, reason="Versión antigua"),
            ).status_code,
            400,
        )
        self.assertEqual(Decimal(self.state()["summary"]["total"]), Decimal("400"))
        with algyre.connect(algyre.DATA / "algyre.sqlite") as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM calculations").fetchone()[0], 2
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM events WHERE action='corrected'"
                ).fetchone()[0],
                1,
            )

    def test_facility_historical_country_and_categories_protected(self):
        self.post("consumptions", self.record())
        d = dict(
            name="Instalación QA",
            country="FR",
            ownership="rented",
            categories=["electricity", "diesel"],
        )
        self.assertEqual(self.post("facilities/" + self.fid, d).status_code, 400)
        d.update(country="ES", categories=["diesel"])
        self.assertEqual(self.post("facilities/" + self.fid, d).status_code, 400)

    def test_pdf_extract_dedup_and_protected_download(self):
        content = self.pdf()
        data = dict(name="factura-qa.pdf", content=base64.b64encode(content).decode())
        r = self.post("documents", data)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(r.json["extracted"]["quantity"]), Decimal("1250.50"))
        self.assertEqual(r.json["extracted"]["start"], "2026-01-01")
        self.assertEqual(self.post("documents", data).status_code, 409)
        self.assertEqual(
            self.c.get("/api/documents/" + r.json["id"] + "/file").data, content
        )
        self.assertEqual(
            self.post(
                "documents",
                dict(name="x.pdf", content=base64.b64encode(b"not pdf").decode()),
            ).status_code,
            400,
        )

    def test_csv_dryrun_confirm_once_and_formula_escape(self):
        body = "instalacion;categoria;cantidad;unidad;inicio;fin;proveedor;referencia;notas\nInstalación QA;electricity;1250,5;kWh;2026-01-01;2026-01-31;=SUM(1);QA-CSV;\n"
        r = self.post("import/preview", {"text": body})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.json["count"], 1)
        self.assertEqual(len(self.state()["records"]), 0)
        token = r.json["token"]
        self.assertEqual(
            self.post("import/confirm", dict(token=token, reviewed=True)).status_code,
            200,
        )
        self.assertEqual(
            self.post("import/confirm", dict(token=token, reviewed=True)).status_code,
            400,
        )
        exported = self.c.get("/api/export.csv?year=2026").data.decode("utf-8-sig")
        self.assertIn("1250.5", exported)
        self.assertTrue(
            algyre.csv_response([{"v": "=SUM(1)"}], ["v"], "x.csv")
            .get_data(as_text=True)
            .endswith("'=SUM(1)\r\n")
        )

    def test_csv_duplicates_inside_preview_and_atomic_failure(self):
        body = "instalacion;categoria;cantidad;unidad;inicio;fin\nInstalación QA;electricity;100;kWh;2026-01-01;2026-01-31\nInstalación QA;electricity;100;kWh;2026-01-01;2026-01-31\n"
        r = self.post("import/preview", {"text": body})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.json["rows"][1]["error"])
        self.assertEqual(
            self.post(
                "import/confirm", dict(token=r.json["token"], reviewed=True)
            ).status_code,
            400,
        )
        self.assertEqual(len(self.state()["records"]), 0)

    def test_immutable_report_stale_after_correction(self):
        self.factor()
        rid = self.post("consumptions", self.record()).json["id"]
        report = self.post("reports", {"year": 2026}).json["id"]
        before = self.c.get("/api/reports/" + report + "/pdf")
        self.assertEqual(before.status_code, 200)
        text = " ".join(
            p.extract_text() for p in PdfReader(io.BytesIO(before.data)).pages
        )
        self.assertIn("200.000", text)
        self.post(
            "consumptions/" + rid,
            self.record(quantity="2000", revision=1, reason="Prueba"),
        )
        self.assertTrue(self.state()["reports"][0]["stale"])
        after = self.c.get("/api/reports/" + report + "/pdf")
        self.assertEqual(
            " ".join(p.extract_text() for p in PdfReader(io.BytesIO(after.data)).pages),
            text,
        )

    def test_backup_restore_roundtrip_and_auth_preserved(self):
        self.factor()
        self.post("consumptions", self.record())
        backup = self.c.get("/api/backup").data
        self.post(
            "consumptions",
            self.record(reference="FEB", start="2026-02-01", end="2026-02-28"),
        )
        r = self.post(
            "restore",
            {"content": base64.b64encode(backup).decode(), "confirmation": "RESTAURAR"},
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(self.state()["records"]), 1)
        self.assertTrue(list(algyre.DATA.glob("antes-restauracion-*.zip")))
        self.post("logout", {})
        self.assertEqual(
            self.c.post(
                "/api/login", json={"password": "fixture-only-password"}
            ).status_code,
            200,
        )

    def test_invalid_restore_does_not_mutate(self):
        self.post("consumptions", self.record())
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as z:
            z.writestr("../escape.json", "{}")
        self.assertEqual(
            self.post(
                "restore",
                {
                    "content": base64.b64encode(raw.getvalue()).decode(),
                    "confirmation": "RESTAURAR",
                },
            ).status_code,
            400,
        )
        self.assertEqual(len(self.state()["records"]), 1)

    def test_demo_backup_cannot_enter_real_workspace(self):
        raw = self.c.get("/api/backup").data
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            payload = json.loads(z.read("algyre.json"))
        payload["workspace"] = "demo"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("algyre.json", json.dumps(payload))
        r = self.post(
            "restore",
            {
                "content": base64.b64encode(buf.getvalue()).decode(),
                "confirmation": "RESTAURAR",
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("mezclar", r.json["error"])

    def test_partial_month_is_not_covered(self):
        self.post("consumptions", self.record(start="2026-01-15"))
        self.assertEqual(self.state()["summary"]["covered"], 0)

    def test_demo_is_separate(self):
        self.post("consumptions", self.record())
        algyre.seed_demo()
        r = self.c.post("/api/demo", json={})
        self.csrf = r.json["csrf"]
        s = self.state()
        self.assertTrue(s["demo"])
        self.assertEqual(len(s["records"]), 27)
        self.post("logout", {})
        r = self.c.post("/api/login", json={"password": "fixture-only-password"})
        self.csrf = r.json["csrf"]
        self.assertEqual(len(self.state()["records"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
