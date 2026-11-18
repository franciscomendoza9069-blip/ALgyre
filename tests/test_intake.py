"""End-to-end import invariants on isolated databases."""

import base64
import io
import json
import time
import unittest
from datetime import datetime

import test_app
from openpyxl import Workbook, load_workbook

algyre = test_app.algyre


class IntakeTests(unittest.TestCase):
    setUp = test_app.LedgerTests.setUp
    tearDown = test_app.LedgerTests.tearDown
    post = test_app.LedgerTests.post
    state = test_app.LedgerTests.state
    record = test_app.LedgerTests.record
    factor = test_app.LedgerTests.factor
    pdf = test_app.LedgerTests.pdf

    def upload(self, rows=None, name="consumos.xlsx", csv=None):
        if csv is not None:
            raw = csv.encode("utf-8-sig")
        else:
            book = Workbook()
            ws = book.active
            ws.title = "Consumos"
            for row in rows or [
                [
                    "Facility",
                    "Quantity",
                    "Start date",
                    "End date",
                    "Invoice ID (optional)",
                ],
                [
                    "Instalación QA",
                    1250.5,
                    datetime(2026, 1, 1),
                    datetime(2026, 1, 31),
                    "XLSX-1",
                ],
            ]:
                ws.append(row)
            book.create_sheet("Ayuda").append(["Solo ayuda"])
            output = io.BytesIO()
            book.save(output)
            book.close()
            raw = output.getvalue()
        r = self.post(
            "import/inspect", dict(name=name, content=base64.b64encode(raw).decode())
        )
        self.assertEqual(r.status_code, 200, r.data)
        return r.json

    def config(self, upload, **extra):
        result = dict(
            token=upload["token"],
            mapping=upload["mapping"],
            defaults=dict(category="electricity", unit="kWh"),
            edits={},
        )
        result.update(extra)
        return result

    def test_excel_dates_mapping_calculation_and_trace(self):
        self.factor()
        upload = self.upload()
        self.assertEqual(upload["sheets"], ["Consumos", "Ayuda"])
        self.assertEqual(upload["mapping"]["reference"], "4")
        r = self.post("import/validate", self.config(upload))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.json["errors"], 0)
        self.assertEqual(self.state()["records"], [])
        confirmed = self.post(
            "import/confirm", dict(token=r.json["token"], reviewed=True)
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.assertEqual(confirmed.json["years"], [2026])
        rec = self.state()["records"][0]
        self.assertEqual(rec["quantity"], "1250.5")
        self.assertEqual(rec["kg_co2e"], "250.10")
        history = self.c.get("/api/consumptions/" + rec["id"] + "/history").json
        self.assertIn("fila 2", history["events"][0]["reason"])
        provenance = json.loads(history["imports"][0]["after_json"])
        self.assertEqual(provenance["sheet"], "Consumos")
        self.assertEqual(len(provenance["sha256"]), 64)
        self.assertEqual(
            self.post(
                "import/confirm", dict(token=r.json["token"], reviewed=True)
            ).status_code,
            400,
        )

    def test_edit_bad_row_revalidate_invalidates_old_token(self):
        upload = self.upload(
            rows=[
                ["instalacion", "cantidad", "inicio", "fin"],
                ["No existe", "mal", "01/01/2026", "31/01/2026"],
            ]
        )
        cfg = self.config(upload)
        old = self.post("import/validate", cfg).json
        self.assertEqual(old["errors"], 1)
        cfg["edits"] = {"2": dict(facility="Instalación QA", quantity="1.250,50")}
        new = self.post("import/validate", cfg)
        self.assertEqual(new.status_code, 200, new.data)
        self.assertEqual(new.json["errors"], 0)
        self.assertEqual(new.json["rows"][0]["values"]["quantity"], "1250.50")
        self.assertEqual(
            self.post(
                "import/confirm", dict(token=old["token"], reviewed=True)
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                "import/confirm", dict(token=new.json["token"], reviewed=True)
            ).status_code,
            200,
        )

    def test_duplicates_in_workbook_block_all_rows(self):
        upload = self.upload(
            rows=[
                ["instalacion", "cantidad", "inicio", "fin"],
                ["Instalación QA", 100, "2026-01-01", "2026-01-31"],
                ["Instalación QA", 100, "2026-01-01", "2026-01-31"],
            ]
        )
        r = self.post("import/validate", self.config(upload)).json
        self.assertEqual(r["errors"], 1)
        self.assertEqual(
            self.post(
                "import/confirm", dict(token=r["token"], reviewed=True)
            ).status_code,
            400,
        )
        self.assertEqual(self.state()["records"], [])

    def test_changed_ledger_rolls_back_entire_commit(self):
        upload = self.upload(
            rows=[
                ["instalacion", "cantidad", "inicio", "fin", "referencia"],
                ["Instalación QA", 100, "2026-01-01", "2026-01-31", "JAN"],
                ["Instalación QA", 100, "2026-02-01", "2026-02-28", "FEB"],
            ]
        )
        r = self.post("import/validate", self.config(upload)).json
        self.assertEqual(r["errors"], 0)
        self.post(
            "consumptions",
            self.record(start="2026-02-01", end="2026-02-28", reference="OTHER"),
        )
        self.assertEqual(
            self.post(
                "import/confirm", dict(token=r["token"], reviewed=True)
            ).status_code,
            400,
        )
        records = self.state()["records"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["reference"], "OTHER")

    def test_csv_with_english_headers_and_ignored_columns(self):
        upload = self.upload(
            name="datos.csv",
            csv="Facility;Quantity;Start date;End date;Amount (optional)\nInstalación QA;1.234,56;01/01/2026;31/01/2026;99\n",
        )
        result = self.post("import/validate", self.config(upload)).json
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["ignored"], ["Amount (optional)"])
        self.assertEqual(result["rows"][0]["values"]["quantity"], "1234.56")

    def test_formula_rejected_not_calculated(self):
        upload = self.upload(
            rows=[
                ["instalacion", "cantidad", "inicio", "fin"],
                ["Instalación QA", "=100*2", "2026-01-01", "2026-01-31"],
            ]
        )
        result = self.post("import/validate", self.config(upload)).json
        self.assertEqual(result["errors"], 1)
        self.assertIn("fórmulas", result["rows"][0]["error"])

    def test_warning_without_factor_or_evidence_is_explicit(self):
        result = self.post(
            "import/validate",
            self.config(self.upload(), defaults=dict(category="electricity")),
        ).json
        warnings = result["rows"][0]["warnings"]
        self.assertEqual(len(warnings), 3)
        self.assertTrue(any("kWh" in v for v in warnings))
        self.assertEqual(result["errors"], 0)

    def test_uploaded_document_can_be_linked_and_preserved_in_backup(self):
        doc = self.post(
            "documents",
            dict(name="evidencia.pdf", content=base64.b64encode(self.pdf()).decode()),
        ).json["id"]
        cfg = self.config(self.upload(), edits={"2": {"document": "evidencia.pdf"}})
        result = self.post("import/validate", cfg).json
        self.assertFalse(any("PDF" in w for w in result["rows"][0]["warnings"]))
        self.post("import/confirm", dict(token=result["token"], reviewed=True))
        self.assertEqual(self.state()["records"][0]["document_id"], doc)
        backup = self.c.get("/api/backup").data
        self.assertEqual(
            self.post(
                "restore",
                dict(
                    content=base64.b64encode(backup).decode(), confirmation="RESTAURAR"
                ),
            ).status_code,
            200,
        )
        history = self.c.get(
            "/api/consumptions/" + self.state()["records"][0]["id"] + "/history"
        ).json
        self.assertEqual(len(history["imports"]), 1)

    def test_session_isolation_expiry_and_csrf(self):
        upload = self.upload()
        cfg = self.config(upload)
        other = algyre.app.test_client()
        r = other.post("/api/demo", json={})
        self.assertEqual(
            other.post(
                "/api/import/validate",
                json=cfg,
                headers={"X-CSRF-Token": r.json["csrf"]},
            ).status_code,
            400,
        )
        self.assertEqual(self.c.post("/api/import/inspect", json={}).status_code, 403)
        algyre.UPLOADS[upload["token"]]["time"] = time.time() - 1801
        self.assertEqual(self.post("import/validate", cfg).status_code, 400)

    def test_unsupported_category_and_cross_year_blocked(self):
        for edits in ({"category": "agua"}, {"end": "2027-01-31"}, {"quantity": "NaN"}):
            result = self.post(
                "import/validate", self.config(self.upload(), edits={"2": edits})
            ).json
            self.assertEqual(result["errors"], 1)

    def test_invalid_files_and_limits(self):
        for name, raw in [
            ("datos.xls", b"fake"),
            ("datos.xlsx", b"fake"),
            ("datos.csv", b"a;a\n1;2"),
        ]:
            r = self.post(
                "import/inspect",
                dict(name=name, content=base64.b64encode(raw).decode()),
            )
            self.assertEqual(r.status_code, 400, r.data)
        rows = [["instalacion", "cantidad", "inicio", "fin"]] + [
            ["Instalación QA", 1, "2026-01-01", "2026-01-31"]
        ] * 501
        book = Workbook()
        ws = book.active
        for row in rows:
            ws.append(row)
        output = io.BytesIO()
        book.save(output)
        self.assertEqual(
            self.post(
                "import/inspect",
                dict(
                    name="muchos.xlsx",
                    content=base64.b64encode(output.getvalue()).decode(),
                ),
            ).status_code,
            400,
        )

    def test_history_all_revisions_and_private_template(self):
        rid = self.post("consumptions", self.record()).json["id"]
        self.post(
            "consumptions/" + rid,
            self.record(quantity="1200", revision=1, reason="Lectura corregida"),
        )
        history = self.c.get("/api/consumptions/" + rid + "/history").json
        self.assertEqual(len(history["events"]), 2)
        self.assertEqual(history["events"][0]["action"], "corrected")
        other = algyre.app.test_client()
        self.assertEqual(
            other.get("/api/consumptions/" + rid + "/history").status_code, 401
        )
        self.assertEqual(other.get("/api/template.xlsx").status_code, 401)
        response = self.c.get("/api/template.xlsx")
        book = load_workbook(io.BytesIO(response.data))
        self.assertEqual(book.sheetnames, ["Consumos", "Ayuda"])
        book.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
