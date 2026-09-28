import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from repo_doctor.cli import main
from repo_doctor.deepseek import DeepSeekError


class DoctorCliTests(unittest.TestCase):
    def run_doctor(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(["doctor", *map(str, args), "--json"])
        return status, json.loads(stdout.getvalue()), stderr.getvalue()

    def test_default_check_is_offline_and_does_not_expose_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.list_models"
            ) as client:
                status, report, stderr = self.run_doctor(root)

        self.assertEqual(status, 0, stderr)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["repository"]["python_files"], 1)
        self.assertEqual(report["repository"]["parse_errors"], 0)
        self.assertEqual(report["deepseek"], {
            "checked": False,
            "key_present": True,
            "model": "deepseek-flash",
            "status": "not_checked",
        })
        self.assertTrue(report["python"]["supported"])
        self.assertNotIn("test-secret", json.dumps(report) + stderr)
        client.assert_not_called()

    def test_explicit_check_with_missing_key_is_actionable_and_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch(
                "repo_doctor.cli.list_models"
            ) as client:
                status, report, stderr = self.run_doctor(root, "--deepseek")

        self.assertEqual(status, 1, stderr)
        self.assertEqual(report["deepseek"]["status"], "missing_key")
        self.assertIn("DEEPSEEK_API_KEY", report["deepseek"]["action"])
        self.assertNotIn("api_key", report["deepseek"])
        client.assert_not_called()

    def test_explicit_check_reports_selected_model_availability(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("x = 1\n", encoding="utf-8")
            environment = {"DEEPSEEK_API_KEY": "test-secret", "DEEPSEEK_MODEL": "custom-model"}
            with patch.dict(os.environ, environment, clear=True), patch(
                "repo_doctor.cli.list_models", return_value=("deepseek-flash", "custom-model")
            ) as client:
                status, report, stderr = self.run_doctor(root, "--deepseek")

        self.assertEqual(status, 0, stderr)
        self.assertEqual(report["deepseek"]["status"], "ready")
        self.assertEqual(report["deepseek"]["model"], "custom-model")
        self.assertNotIn("test-secret", json.dumps(report) + stderr)
        client.assert_called_once_with(api_key="test-secret", timeout=10.0)

    def test_explicit_check_categorizes_provider_failure_without_leaking_details(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("x = 1\n", encoding="utf-8")
            error = DeepSeekError("DeepSeek API returned HTTP 401", code="http", http_status=401)
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.list_models", side_effect=error
            ):
                status, report, stderr = self.run_doctor(root, "--deepseek")

        self.assertEqual(status, 1, stderr)
        self.assertEqual(report["deepseek"]["status"], "error")
        self.assertEqual(report["deepseek"]["category"], "authentication")
        self.assertEqual(report["deepseek"]["http_status"], 401)
        self.assertIn("DEEPSEEK_API_KEY", report["deepseek"]["action"])
        self.assertNotIn("test-secret", json.dumps(report) + stderr)

    def test_explicit_check_fails_when_selected_model_is_not_listed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.list_models", return_value=("deepseek-flash",)
            ):
                status, report, stderr = self.run_doctor(root, "--deepseek", "--model", "missing-model")

        self.assertEqual(status, 1, stderr)
        self.assertEqual(report["deepseek"]["status"], "model_unavailable")
        self.assertEqual(report["deepseek"]["model"], "missing-model")
        self.assertIn("DEEPSEEK_MODEL", report["deepseek"]["action"])

    def test_parse_failure_prevents_ready_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.py").write_text("def broken(:\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                status, report, stderr = self.run_doctor(root)

        self.assertEqual(status, 1, stderr)
        self.assertEqual(report["repository"]["parse_errors"], 1)

    def test_malformed_key_is_reported_safely(self):
        secret = "DEMOSECRET\nEXTRA"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("x = 1\n", encoding="utf-8")
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": secret}, clear=True), patch(
                "urllib.request.OpenerDirector.open"
            ) as open_request:
                status, report, stderr = self.run_doctor(root, "--deepseek")

        self.assertEqual(status, 1, stderr)
        self.assertEqual(report["deepseek"]["category"], "invalid_key")
        self.assertNotIn(secret, json.dumps(report) + stderr)
        open_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
