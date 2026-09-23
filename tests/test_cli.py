import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
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
