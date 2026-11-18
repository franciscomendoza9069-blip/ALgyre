"""Environmental accounting and upgrades against isolated, synthetic ledgers."""

import base64
import io
import json
import sqlite3
import unittest
from decimal import Decimal

from pypdf import PdfReader
import test_app
from algyre_core.environment import ACTIVITIES, UNIT_LABELS

algyre = test_app.algyre


class EnvironmentTests(unittest.TestCase):
    setUp = test_app.LedgerTests.setUp
    tearDown = test_app.LedgerTests.tearDown
    post = test_app.LedgerTests.post
    state = test_app.LedgerTests.state
    record = test_app.LedgerTests.record
    factor = test_app.LedgerTests.factor

    def enable(self, categories):
        response = self.post(
            "facilities/" + self.fid,
            dict(
                name="Instalación QA",
                country="ES",
                categories=["electricity", "diesel", *categories],
            ),
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_three_scopes_units_exports_and_reports(self):
        self.enable(
            [
                "refrigerant",
                "heat",
                "waste",
                "business_travel",
                "water",
                "upstream_transport",
                "purchased_goods",
                "commuting",
                "cooling",
            ]
        )
        samples = [
            ("refrigerant", "kg", "2", "kg", "100", "200"),
            ("heat", "MWh", "1.5", "kWh", "0.1", "150"),
            ("waste", "t", "0.5", "kg", "2", "1000"),
            ("business_travel", "pkm", "30", "pkm", "0.1", "3"),
            ("water", "m3", "10", "m3", "0.2", "2"),
            ("upstream_transport", "tkm", "100", "tkm", "0.03", "3"),
            ("purchased_goods", "unit", "2", "unit", "5", "10"),
            ("commuting", "km", "10", "km", "0.2", "2"),
            ("cooling", "kWh", "5", "kWh", "0.2", "1"),
        ]
        for cat, unit, quantity, factor_unit, value, expected in samples:
            factor = self.factor(category=cat, unit=factor_unit, value=value)
            result = self.post(
                "consumptions",
                self.record(
                    category=cat,
                    unit=unit,
                    quantity=quantity,
                    factor_id=factor,
                    note="Actividad y factor ficticios solo para pruebas.",
                    reference=cat,
                ),
            )
            self.assertEqual(result.status_code, 200, result.data)
            record = next(r for r in self.state()["records"] if r["category"] == cat)
            self.assertEqual(Decimal(record["kg_co2e"]), Decimal(expected))
            self.assertEqual(record["scope"], ACTIVITIES[cat].scope)
        summary = self.state()["summary"]
        self.assertEqual(Decimal(summary["scope1"]), Decimal("200"))
        self.assertEqual(Decimal(summary["scope2"]), Decimal("151"))
        self.assertEqual(Decimal(summary["scope3"]), Decimal("1020"))
        self.assertEqual(Decimal(summary["total"]), Decimal("1371"))
        csv = self.c.get("/api/export.csv?year=2026").data.decode("utf-8-sig")
        self.assertIn("categoria_alcance3", csv)
        report = self.post("reports", dict(year=2026)).json["id"]
        pdf = self.c.get("/api/reports/" + report + "/pdf")
        body = " ".join(
            page.extract_text() for page in PdfReader(io.BytesIO(pdf.data)).pages
        )
        self.assertIn("Alcance 3 incluido", body)
        self.assertIn("1,020.000", body)

    def test_new_activities_require_deliberate_factor_selection(self):
        self.enable(["waste"])
        factor = self.factor(category="waste", unit="kg", value="2")
        result = self.post(
            "consumptions",
            self.record(
                category="waste",
                unit="kg",
                note="Papel tratado externamente, dato de prueba.",
            ),
        )
        self.assertEqual(result.status_code, 200, result.data)
        state = self.state()
        self.assertIsNone(state["records"][0]["kg_co2e"])
        self.assertEqual(state["summary"]["pending"], 1)
        result = self.post(
            "consumptions/" + result.json["id"],
            self.record(
                category="waste",
                unit="kg",
                note="Papel tratado externamente, dato de prueba.",
                factor_id=factor,
                revision=1,
                reason="Seleccionar factor específico",
            ),
        )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(self.state()["summary"]["pending"], 0)

    def test_rejects_incompatible_units_missing_context_and_negative_factors(self):
        self.enable(["refrigerant", "business_travel"])
        for changes in [
            dict(category="refrigerant", unit="L", note="Test"),
            dict(category="refrigerant", unit="kg"),
            dict(category="business_travel", unit="L", note="Test"),
        ]:
            self.assertEqual(
                self.post("consumptions", self.record(**changes)).status_code, 400
            )
        self.assertEqual(
            self.post(
                "factors", dict(category="waste", unit="kg", value="-1")
            ).status_code,
            400,
        )
        factor = self.factor(category="business_travel", unit="pkm")
        response = self.post(
            "consumptions",
            self.record(
                category="business_travel", unit="km", note="Prueba", factor_id=factor
            ),
        )
        self.assertEqual(response.status_code, 400)

    def test_distinct_events_same_dates_and_real_duplicates(self):
        self.enable(["business_travel"])
        first = self.record(
            category="business_travel",
            unit="pkm",
            note="Viaje de prueba",
            reference="VIAJE-1",
        )
        self.assertEqual(self.post("consumptions", first).status_code, 200)
        second = dict(first, reference="VIAJE-2")
        self.assertEqual(self.post("consumptions", second).status_code, 200)
        self.assertEqual(self.post("consumptions", second).status_code, 400)
        unreferenced = dict(first, reference="", quantity="25")
        self.assertEqual(self.post("consumptions", unreferenced).status_code, 200)
        self.assertEqual(self.post("consumptions", unreferenced).status_code, 400)
        self.assertEqual(
            self.post(
                "consumptions",
                dict(
                    unreferenced,
                    allow_overlap=True,
                    note="Dos actividades distintas revisadas",
                ),
            ).status_code,
            200,
        )

    def test_import_distinct_events_sharing_a_day(self):
        self.enable(["waste"])
        raw = "Instalación,Categoría,Cantidad,Unidad,Inicio,Fin,Referencia,Notas\nInstalación QA,waste,1,kg,2026-01-01,2026-01-01,ALBARAN-1,Papel de prueba\nInstalación QA,waste,1,kg,2026-01-01,2026-01-01,ALBARAN-2,Envase de prueba\n"
        upload = self.post(
            "import/inspect",
            dict(name="residuos.csv", content=base64.b64encode(raw.encode()).decode()),
        ).json
        preview = self.post(
            "import/validate",
            dict(
                token=upload["token"], mapping=upload["mapping"], defaults={}, edits={}
            ),
        )
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.json["errors"], 0, preview.json)
        confirmed = self.post(
            "import/confirm", dict(token=preview.json["token"], reviewed=True)
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.assertEqual(len(self.state()["records"]), 2)

    def test_event_activities_do_not_create_false_monthly_gaps(self):
        self.enable(["waste", "business_travel", "refrigerant"])
        self.assertEqual(self.state()["summary"]["expected"], 24)
        self.assertFalse(
            any(
                "Residuos" in gap["category"] for gap in self.state()["summary"]["gaps"]
            )
        )

    def test_import_new_activity_pending_then_backup_restore(self):
        self.enable(["waste"])
        raw = "Instalación,Categoría,Cantidad,Unidad,Inicio,Fin,Notas\nInstalación QA,waste,0.5,t,2026-01-01,2026-01-01,Papel reciclado por tercero de prueba\n"
        upload = self.post(
            "import/inspect",
            dict(name="residuos.csv", content=base64.b64encode(raw.encode()).decode()),
        ).json
        preview = self.post(
            "import/validate",
            dict(
                token=upload["token"], mapping=upload["mapping"], defaults={}, edits={}
            ),
        )
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.json["errors"], 0, preview.json)
        result = self.post(
            "import/confirm", dict(token=preview.json["token"], reviewed=True)
        )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(self.state()["summary"]["pending"], 1)
        archive = self.c.get("/api/backup").data
        restored = self.post(
            "restore",
            dict(content=base64.b64encode(archive).decode(), confirmation="RESTAURAR"),
        )
        self.assertEqual(restored.status_code, 200, restored.data)
        self.assertEqual(self.state()["records"][0]["unit"], "t")

    def test_legacy_migration_preserves_records_reports_auth_and_foreign_keys(self):
        self.factor()
        self.post("consumptions", self.record())
        self.post("reports", dict(year=2026))
        path = algyre.DATA / "legacy.sqlite"
        schema = (algyre.ROOT / "schema.sql").read_text("utf-8")
        schema = schema.replace(
            ",".join(repr(k) for k in ACTIVITIES),
            "'electricity','gas','diesel','petrol'",
        )
        schema = schema.replace(
            ",".join(repr(k) for k in UNIT_LABELS if k not in ("MWh", "t")),
            "'kWh','L','kg','m3'",
        )
        schema = schema.replace(
            ",".join(repr(k) for k in UNIT_LABELS), "'kWh','MWh','L','kg','m3'"
        )
        with (
            algyre.connect(algyre.DATA / "algyre.sqlite") as source,
            sqlite3.connect(path) as legacy,
        ):
            legacy.executescript(schema)
            for table in ["auth", *algyre.TABLES]:
                for row in source.execute("SELECT * FROM " + table):
                    algyre.insert(legacy, table, dict(row))
        legacy.close()
        algyre.initialize(path)
        algyre.initialize(path)
        self.assertTrue((path.parent / "antes-alcance-v2-legacy.sqlite").is_file())
        with algyre.connect(path) as upgraded:
            self.assertIsNone(upgraded.execute("PRAGMA foreign_key_check").fetchone())
            self.assertEqual(
                upgraded.execute("SELECT COUNT(*) FROM consumptions").fetchone()[0], 1
            )
            self.assertEqual(
                upgraded.execute("SELECT COUNT(*) FROM reports").fetchone()[0], 1
            )
            self.assertEqual(
                upgraded.execute("SELECT COUNT(*) FROM auth").fetchone()[0], 1
            )
            self.assertIn(
                "refrigerant",
                upgraded.execute(
                    "SELECT sql FROM sqlite_master WHERE name='factors'"
                ).fetchone()[0],
            )
