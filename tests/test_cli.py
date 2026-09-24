import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from repo_doctor.cli import main
from repo_doctor.deepseek import DeepSeekError, DeepSeekResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_main(self, *arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(list(map(str, arguments)))
        return status, stdout.getvalue(), stderr.getvalue()

    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "repo_doctor", *map(str, arguments)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

    def make_repo(self, root):
        (root / "a.py").write_text("def target():\n    return 1\n", encoding="utf-8")
        (root / "b.py").write_text(
            "from a import target\n\ndef run():\n    return target()\n", encoding="utf-8"
        )

    def test_scan_json_exposes_symbols_and_grounded_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)

            result = self.run_cli("scan", root, "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["stats"]["python_files"], 2)
        self.assertIn("a.py::target", [item["id"] for item in report["symbols"]])
        self.assertEqual(report["call_edges"], [{"caller": "b.py::run", "callee": "a.py::target", "line": 4}])

    def test_context_text_contains_numbered_source_and_prompt_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)

            result = self.run_cli("context", root, "a.py::target", "--max-lines", "8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("a.py::target", result.stdout)
        self.assertIn("2 |     return 1", result.stdout)
        self.assertIn("evidence", result.stdout)

    def test_validate_rejection_uses_nonzero_exit_and_explains_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            finding = {
                "title": "Example",
                "category": "reliability",
                "confidence": 0.8,
                "evidence": [{"file": "a.py", "start_line": 2, "end_line": 2, "quote": "not in source"}],
                "reasoning": "Example reasoning",
                "impact": "Example impact",
                "suggested_fix": "Example fix",
            }
            path = root / "findings.json"
            path.write_text(json.dumps(finding), encoding="utf-8")

            result = self.run_cli("validate", root, path, "--json")

        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["accepted"], [])
        self.assertIn("quote", " ".join(report["rejected"][0]["reasons"]))

    def test_unknown_symbol_returns_usage_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)

            result = self.run_cli("impact", root, "missing.py::thing")

        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown symbol", result.stderr)

    def test_diagnose_json_uses_client_and_keeps_preflight_out_of_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            finding = {
                "title": "Example issue",
                "category": "reliability",
                "confidence": 0.8,
                "evidence": [{
                    "file": "a.py",
                    "start_line": 2,
                    "end_line": 2,
                    "quote": "    return 1",
                    "symbol": "a.py::target",
                }],
                "reasoning": "The line produces this value.",
                "impact": "Callers receive this value.",
                "suggested_fix": "Review the return value.",
            }
            response = DeepSeekResult("deepseek-flash", {"findings": [finding]})

            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json", return_value=response, create=True
            ) as client:
                status, stdout, stderr = self.run_main("diagnose", root, "a.py::target", "--json")

        self.assertEqual(status, 0, stderr)
        report = json.loads(stdout)
        self.assertEqual(
            set(report),
            {"schema_version", "provider", "model", "accepted", "rejected"},
        )
        self.assertEqual(report["provider"], "deepseek")
        self.assertEqual(report["model"], "deepseek-flash")
        self.assertEqual(len(report["accepted"]), 1)
        self.assertEqual(report["rejected"], [])
        self.assertIn("a.py", stderr)
        self.assertNotIn("return 1", stderr)
        self.assertNotIn("test-secret", stdout + stderr)
        client.assert_called_once()
        self.assertEqual(client.call_args.kwargs["api_key"], "test-secret")

    def test_diagnose_model_precedence_is_flag_then_environment_then_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            cases = [
                (("--model", "command-model"), {"DEEPSEEK_MODEL": "environment-model"}, "command-model"),
                ((), {"DEEPSEEK_MODEL": "environment-model"}, "environment-model"),
                ((), {}, "deepseek-flash"),
            ]
            for arguments, model_environment, expected_model in cases:
                with self.subTest(expected_model=expected_model):
                    environment = {"DEEPSEEK_API_KEY": "test-secret", **model_environment}
                    response = DeepSeekResult("reported-model", {"findings": []})
                    with patch.dict(os.environ, environment, clear=True), patch(
                        "repo_doctor.cli.complete_json", return_value=response, create=True
                    ) as client:
                        status, _, stderr = self.run_main(
                            "diagnose", root, "a.py::target", *arguments
                        )

                    self.assertEqual(status, 0, stderr)
                    self.assertEqual(client.call_args.kwargs["model"], expected_model)

    def test_missing_key_and_invalid_line_limits_do_not_call_client(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)

            cases = [
                ({}, ("diagnose", root, "a.py::target"), "DEEPSEEK_API_KEY"),
                ({"DEEPSEEK_API_KEY": "key"}, ("diagnose", root, "a.py::target", "--max-lines", "0"), "1 through 120"),
                ({"DEEPSEEK_API_KEY": "key"}, ("diagnose", root, "a.py::target", "--max-lines", "121"), "1 through 120"),
            ]
            for environment, arguments, message in cases:
                with self.subTest(arguments=arguments):
                    with patch.dict(os.environ, environment, clear=True), patch(
                        "repo_doctor.cli.complete_json", create=True
                    ) as client:
                        status, _, stderr = self.run_main(*arguments)

                    self.assertEqual(status, 2)
                    self.assertIn(message, stderr)
                    client.assert_not_called()

    def test_unknown_or_ambiguous_symbol_does_not_call_client(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            (root / "ambiguous.py").write_text(
                "def target():\n    return 1\n\ndef target():\n    return 2\n",
                encoding="utf-8",
            )
            for symbol in ("missing.py::unknown", "ambiguous.py::target"):
                with self.subTest(symbol=symbol):
                    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "key"}, clear=True), patch(
                        "repo_doctor.cli.complete_json", create=True
                    ) as client:
                        status, _, _ = self.run_main("diagnose", root, symbol)

                    self.assertEqual(status, 2)
                    client.assert_not_called()

    def test_context_over_64_kib_does_not_call_client(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            huge_string = "x" * 65536
            (root / "huge.py").write_text(
                "def target():\n    return '" + huge_string + "'\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "key"}, clear=True), patch(
                "repo_doctor.cli.complete_json", create=True
            ) as client:
                status, _, stderr = self.run_main("diagnose", root, "huge.py::target")

        self.assertEqual(status, 2)
        self.assertIn("64 KiB", stderr)
        client.assert_not_called()

    def test_provider_error_is_sanitized_and_rejected_finding_returns_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)

            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json",
                side_effect=DeepSeekError("DeepSeek API returned HTTP 401"),
                create=True,
            ):
                status, _, stderr = self.run_main("diagnose", root, "a.py::target")

            self.assertEqual(status, 2)
            self.assertIn("HTTP 401", stderr)
            self.assertNotIn("test-secret", stderr)

            bad_finding = {
                "title": "Unproven issue",
                "category": "reliability",
                "confidence": 0.8,
                "evidence": [{"file": "a.py", "start_line": 2, "end_line": 2, "quote": "invented"}],
                "reasoning": "Reasoning.",
                "impact": "Impact.",
                "suggested_fix": "Fix.",
            }
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json",
                return_value=DeepSeekResult("deepseek-flash", {"findings": [bad_finding]}),
                create=True,
            ):
                status, stdout, _ = self.run_main("diagnose", root, "a.py::target", "--json")

        self.assertEqual(status, 1)
        self.assertEqual(json.loads(stdout)["accepted"], [])
        self.assertEqual(len(json.loads(stdout)["rejected"]), 1)

    def test_existing_commands_work_offline_without_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            findings_path = root / "findings.json"
            findings_path.write_text("[]", encoding="utf-8")
            cases = [
                ("scan", root, "--json"),
                ("context", root, "a.py::target", "--json"),
                ("impact", root, "a.py::target", "--json"),
                ("validate", root, findings_path, "--json"),
            ]

            with patch.dict(os.environ, {}, clear=True), patch(
                "repo_doctor.cli.complete_json", create=True
            ) as client:
                for arguments in cases:
                    with self.subTest(command=arguments[0]):
                        status, _, stderr = self.run_main(*arguments)
                        self.assertEqual(status, 0, stderr)

        client.assert_not_called()

    def test_diagnose_help_explains_credentials_and_cloud_data_boundary(self):
        result = self.run_cli("diagnose", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        help_text = " ".join(result.stdout.split())
        for expected in (
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_MODEL",
            "64 KiB",
            "selected source context",
            "selected code may contain secrets",
            "commands remain offline",
            "does not upload the full repository",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, help_text)
