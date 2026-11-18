"""Renaming must preserve local credentials, ledgers and existing backups."""

import base64
import io
import json
import os
import unittest
import zipfile
from unittest.mock import patch

import test_app
from algyre_core.compatibility import load_legacy_environment, local_database

algyre = test_app.algyre


class CompatibilityTests(unittest.TestCase):
    setUp = test_app.LedgerTests.setUp
    tearDown = test_app.LedgerTests.tearDown
    post = test_app.LedgerTests.post
    state = test_app.LedgerTests.state
    record = test_app.LedgerTests.record

    def test_existing_backup_can_be_restored(self):
        self.assertEqual(self.post("consumptions", self.record()).status_code, 200)
        original = self.c.get("/api/backup").data
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            payload = json.loads(archive.read("algyre.json"))
        payload["format"] = "linde-1"
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("linde.json", json.dumps(payload))
        response = self.post(
            "restore",
            {
                "content": base64.b64encode(output.getvalue()).decode(),
                "confirmation": "RESTAURAR",
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(self.state()["records"]), 1)

    def test_existing_database_and_password_remain_accessible(self):
        current = algyre.DATA / "algyre.sqlite"
        previous = algyre.DATA / "linde.sqlite"
        current.rename(previous)
        self.assertEqual(local_database(algyre.DATA), previous)
        self.assertTrue(self.c.get("/api/status").json["configured"])
        self.post("logout", {})
        response = self.c.post("/api/login", json={"password": "fixture-only-password"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(current.exists())

    def test_legacy_environment_and_explicit_new_settings(self):
        with patch.dict(
            os.environ, {"LINDE_PORT": "8765", "LINDE_MODE": "local"}, clear=True
        ):
            load_legacy_environment()
            self.assertEqual(os.environ["ALGYRE_PORT"], "8765")
            self.assertEqual(os.environ["ALGYRE_MODE"], "local")
        with patch.dict(
            os.environ, {"LINDE_PORT": "8765", "ALGYRE_PORT": "8877"}, clear=True
        ):
            load_legacy_environment()
            self.assertEqual(os.environ["ALGYRE_PORT"], "8877")
