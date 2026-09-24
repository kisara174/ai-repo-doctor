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
            (root / "cli.py").write_text(
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@cli.command()\n"
                "def leaf():\n"
                "    pass\n",
                encoding="utf-8",
            )
            (root / "overloads.py").write_text(
                "from typing import overload\n"
                "@overload\n"
                "def parse(value: int) -> int: ...\n"
                "@overload\n"
                "def parse(value: str) -> str: ...\n"
                "def parse(value):\n"
                "    return value\n",
                encoding="utf-8",
            )

            result = self.run_cli("scan", root, "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["stats"]["python_files"], 4)
        self.assertEqual(report["stats"]["resolved_calls"], 1)
        self.assertEqual(report["stats"]["unresolved_calls"], 0)
        self.assertIn("a.py::target", [item["id"] for item in report["symbols"]])
        self.assertEqual(
            report["semantic_edges"],
            [
                {
                    "kind": "reexport",
                    "target_symbol": "a.py::target",
                    "evidence_file": "b.py",
                    "line": 1,
                    "source_symbol": None,
                    "source_file": "b.py",
                    "exported_name": "target",
                },
                {
                    "kind": "command_registration",
                    "target_symbol": "cli.py::leaf",
                    "evidence_file": "cli.py",
                    "line": 5,
                    "source_symbol": "cli.py::cli",
                    "source_file": None,
                    "exported_name": None,
                },
            ],
        )
        target = next(item for item in report["symbols"] if item["id"] == "a.py::target")
        self.assertEqual(target["decorators"], [])
        self.assertEqual(target["overloads"], [])
        group = next(item for item in report["symbols"] if item["id"] == "cli.py::cli")
        self.assertEqual(
            group["decorators"],
            [{"expression": "click.group()", "line": 2, "recognized": "click.group"}],
        )
        parse = next(item for item in report["symbols"] if item["id"] == "overloads.py::parse")
        self.assertEqual(len(parse["overloads"]), 2)
        imported_target = next(item for item in report["imports"] if item["file"] == "b.py")
        self.assertTrue(imported_target["is_unconditional_module_level"])
        self.assertEqual(
            report["call_edges"],
            [{"caller": "b.py::run", "callee": "a.py::target", "line": 4, "via_reexports": []}],
        )

    def test_context_text_contains_numbered_source_and_prompt_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text(
                "from a import target as public\n",
                encoding="utf-8",
            )
            (root / "b.py").write_text(
                "from pkg import public\n\n"
                "def run():\n"
                "    return public()\n",
                encoding="utf-8",
            )

            result = self.run_cli("context", root, "a.py::target", "--max-lines", "8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("a.py::target", result.stdout)
        self.assertIn("2 |     return 1", result.stdout)
        self.assertIn("evidence", result.stdout)
        self.assertIn("Static call edges:", result.stdout)
        self.assertIn("via re-export public at pkg/__init__.py:1", result.stdout)
        self.assertIn("Semantic relationships:", result.stdout)

    def test_context_and_impact_text_label_click_relationships(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@cli.command()\n"
                "def leaf():\n"
                "    pass\n",
                encoding="utf-8",
            )

            context_result = self.run_cli("context", root, "app.py::cli")
            impact_result = self.run_cli("impact", root, "app.py::cli")

        self.assertEqual(context_result.returncode, 0, context_result.stderr)
        self.assertEqual(impact_result.returncode, 0, impact_result.stderr)
        self.assertIn("registered_command: app.py::leaf", context_result.stdout)
        self.assertIn("Semantic relationships:", context_result.stdout)
        self.assertIn("app.py::cli -> app.py::leaf (command_registration)", context_result.stdout)
        self.assertIn("Semantic relationships:", impact_result.stdout)
        self.assertIn("outgoing: app.py::cli -> app.py::leaf", impact_result.stdout)

    def test_context_and_impact_json_use_schema_v2(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)

            context_result = self.run_cli("context", root, "a.py::target", "--json")
            impact_result = self.run_cli("impact", root, "a.py::target", "--json")

        self.assertEqual(context_result.returncode, 0, context_result.stderr)
        self.assertEqual(impact_result.returncode, 0, impact_result.stderr)
        self.assertEqual(json.loads(context_result.stdout)["schema_version"], 2)
        self.assertEqual(json.loads(impact_result.stdout)["schema_version"], 2)

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
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["accepted"], [])
        self.assertIn("quote", " ".join(report["rejected"][0]["reasons"]))

    def test_unknown_symbol_returns_usage_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)

            result = self.run_cli("impact", root, "missing.py::thing")

        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown symbol", result.stderr)
