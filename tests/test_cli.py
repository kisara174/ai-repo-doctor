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

    def test_context_cli_includes_explicit_symbol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Base:\n"
                "    def render(self):\n"
                "        return list(self._list)\n"
                "class Child(Base):\n"
                "    def __iter__(self):\n"
                "        return iter(self.values)\n",
                encoding="utf-8",
            )
            result = self.run_cli(
                "context", root, "app.py::Base.render",
                "--include-symbol", "app.py::Child", "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        blocks = json.loads(result.stdout)["blocks"]
        self.assertEqual(blocks[2]["symbol"], "app.py::Child")
        self.assertEqual(blocks[2]["relation"], "user_selected")
        self.assertIn(
            "        return iter(self.values)",
            [line["text"] for line in blocks[2]["lines"]],
        )

    def test_context_and_impact_json_use_schema_v2(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)

            context_result = self.run_cli("context", root, "a.py::target", "--json")
            impact_result = self.run_cli("impact", root, "a.py::target", "--json")
            impact_text = self.run_cli("impact", root, "a.py::target")

        self.assertEqual(context_result.returncode, 0, context_result.stderr)
        self.assertEqual(impact_result.returncode, 0, impact_result.stderr)
        self.assertEqual(json.loads(context_result.stdout)["schema_version"], 2)
        impact = json.loads(impact_result.stdout)
        self.assertEqual(impact["schema_version"], 2)
        self.assertEqual(impact["affected_symbols"][0]["call_path_evidence"][0]["file"], "b.py")
        self.assertEqual(impact["affected_symbols"][0]["call_path_evidence"][0]["line"], 4)
        self.assertEqual(impact_text.returncode, 0, impact_text.stderr)
        self.assertIn("b.py:4", impact_text.stdout)

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

    def test_validate_text_labels_quote_match_without_claiming_correctness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            finding = {
                "title": "Example issue",
                "category": "reliability",
                "confidence": 0.8,
                "evidence": [{"file": "a.py", "start_line": 2, "end_line": 2, "quote": "    return 1"}],
                "reasoning": "Claim not checked by quote validation.",
                "impact": "Unverified impact.",
                "suggested_fix": "Review manually.",
            }
            path = root / "findings.json"
            path.write_text(json.dumps(finding), encoding="utf-8")
            result = self.run_cli("validate", root, path)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Quote-verified: 1", result.stdout)
        self.assertIn("QUOTE-VERIFIED [0] Example issue", result.stdout)
        self.assertNotIn("ACCEPTED", result.stdout)

    def test_diagnose_text_labels_quote_match_without_claiming_correctness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            finding = {
                "title": "Example issue",
                "category": "reliability",
                "confidence": 0.8,
                "evidence": [{"file": "a.py", "start_line": 2, "end_line": 2, "quote": "    return 1"}],
                "reasoning": "Claim not checked by quote validation.",
                "impact": "Unverified impact.",
                "suggested_fix": "Review manually.",
            }
            response = DeepSeekResult("deepseek-flash", {"findings": [finding]})
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json", return_value=response
            ):
                status, stdout, stderr = self.run_main("diagnose", root, "a.py::target")

        self.assertEqual(status, 0, stderr)
        self.assertIn("Quote-verified: 1", stdout)
        self.assertIn("QUOTE-VERIFIED [0] Example issue", stdout)
        self.assertNotIn("ACCEPTED", stdout)

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
            "doctor without --deepseek remain offline",
            "does not upload the full repository",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, help_text)

    def test_diagnose_schema_format_is_opt_in_and_uses_same_evidence_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            response = DeepSeekResult("deepseek-flash", {"findings": []})
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json_schema", return_value=response, create=True
            ) as schema_client, patch("repo_doctor.cli.complete_json") as chat_client:
                status, stdout, stderr = self.run_main(
                    "diagnose", root, "a.py::target", "--response-format", "json-schema", "--json"
                )

        self.assertEqual(status, 0, stderr)
        self.assertEqual(json.loads(stdout)["accepted"], [])
        self.assertEqual(json.loads(stdout)["rejected"], [])
        self.assertIn("a.py", stderr)
        schema_client.assert_called_once()
        self.assertEqual(schema_client.call_args.kwargs["api_key"], "test-secret")
        chat_client.assert_not_called()

    def test_diagnose_schema_format_rejects_ungrounded_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repo(root)
            finding = {
                "title": "Unsupported claim",
                "category": "reliability",
                "confidence": 0.8,
                "evidence": [{"file": "a.py", "start_line": 2, "end_line": 2, "quote": "invented"}],
                "reasoning": "Reasoning.",
                "impact": "Impact.",
                "suggested_fix": "Fix.",
            }
            response = DeepSeekResult("deepseek-flash", {"findings": [finding]})
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json_schema", return_value=response
            ):
                status, stdout, stderr = self.run_main(
                    "diagnose", root, "a.py::target", "--response-format", "json-schema", "--json"
                )

        self.assertEqual(status, 1, stderr)
        self.assertEqual(json.loads(stdout)["accepted"], [])
        self.assertEqual(len(json.loads(stdout)["rejected"]), 1)

class LanguageCliTests(unittest.TestCase):
    def test_extensionless_index_cli_returns_binding_provenance(self):
        from tests.test_js_ts import HAS_EXTRA
        if not HAS_EXTRA:
            self.skipTest('requires optional js extra')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            (root/'dir').mkdir()
            (root/'dir/index.ts').write_text('export function inc() { return 1; }\n')
            (root/'app.ts').write_text("import {inc} from './dir';\nexport function run() { return inc(); }\n")
            result=self.run_cli('symbols',root,'--query','inc','--languages','typescript','--json')
            self.assertEqual(result.returncode,0,result.stderr)
            sid=json.loads(result.stdout)['matches'][0]['id']
            self.assertEqual(sid,'dir/index.ts::inc')
            for cmd in ('context','impact'):
                result=self.run_cli(cmd,root,sid,'--languages','typescript','--json')
                self.assertEqual(result.returncode,0,result.stderr)
                data=json.loads(result.stdout)
                self.assertFalse(data['analysis']['esm_source_resolution']['runtime_resolution'])
                edge=(data['call_evidence'][0] if cmd=='context'
                      else data['affected_symbols'][0]['call_path_evidence'][0])
                self.assertEqual((edge['caller'],edge['line']),('app.ts::run',2))
                self.assertEqual(edge['via_esm_import']['specifier'],'./dir')
                self.assertEqual(edge['via_esm_import']['resolution_kind'],'unique-directory-index-source')

    def run_cli(self, *args, no_site=False):
        return subprocess.run([sys.executable, *(['-S'] if no_site else []), '-m', 'repo_doctor',
                               *map(str, args)], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30)

    def test_missing_extra_errors_but_default_python_does_not_import_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'a.py').write_text('def entry():\n return 1\n')
            (root / 'a.js').write_text('export function entry() {}')
            normal = self.run_cli('overview', root, '--json', no_site=True)
            missing = self.run_cli('overview', root, '--languages', 'javascript', '--json', no_site=True)
            self.assertEqual(normal.returncode, 0, normal.stderr)
            self.assertEqual(json.loads(normal.stdout)['stats']['python_files'], 1)
            self.assertEqual(missing.returncode, 2)
            self.assertIn('ai-repo-doctor[js]', missing.stderr)

    def test_invalid_languages_and_js_snapshot_reject_before_index_or_write(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_root = Path(directory) / 'does-not-exist'
            out = Path(directory) / 'artifact' / 'snapshot.json'
            for value in ('auto', 'python,', ''):
                result = self.run_cli('overview', missing_root, '--languages', value)
                self.assertEqual(result.returncode, 2)
                self.assertIn('languages', result.stderr)
            result = self.run_cli('context', missing_root, 'a.js::entry', '--languages', 'javascript', '--snapshot-out', out)
            self.assertEqual(result.returncode, 2)
            self.assertIn('--json', result.stderr)
            self.assertIn('snapshot', result.stderr.lower())
            self.assertFalse(out.parent.exists())

    def test_all_five_commands_expose_scope_and_keep_python_counts(self):
        from tests.test_js_ts import HAS_EXTRA
        if not HAS_EXTRA:
            self.skipTest('requires optional js extra')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'a.py').write_text('def entry():\n return 1\n')
            (root / 'a.ts').write_text('export function entry() { return 1; }')
            commands = [('overview',), ('symbols', '--query', 'entry'),
                        ('context', 'a.ts::entry'), ('impact', 'a.ts::entry'),
                        ('map', '--out', root / 'map-output')]
            for command in commands:
                result = self.run_cli(command[0], root, *command[1:], '--languages', 'python,typescript', '--json')
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data['analysis']['files_by_language'], {'python': 1, 'javascript': 0, 'typescript': 1})
                self.assertIn('calls', data['analysis']['capabilities']['typescript'])
                if command[0] == 'overview':
                    self.assertEqual(data['stats']['python_files'], 1)
                    self.assertIn('--languages', data['next_commands']['symbols'])
                elif command[0] == 'map':
                    saved = json.loads(Path(data['map_json']).read_text())
                    self.assertEqual(saved['coverage']['python_files'], 1)
                    self.assertFalse(next(n for n in saved['nodes'] if n['id'] == 'file:a.ts')['python'])
                    self.assertEqual(data['analysis'], saved['analysis'])
                    self.assertTrue(next(n for n in saved['nodes'] if n['id'] == 'file:a.ts')['analyzed'])
                    self.assertFalse(any(r['reason'] == 'map-projection-pending' for r in data['analysis']['limits']))
                elif command[0] == 'impact':
                    self.assertEqual(data['status'], 'bounded')
            terminal = self.run_cli('impact', root, 'a.ts::entry', '--languages', 'typescript')
            self.assertIn('Limited direct', terminal.stdout)
            self.assertIn('typescript', terminal.stdout)

    def test_js_include_and_ambiguous_context_are_explicit(self):
        from tests.test_js_ts import HAS_EXTRA, FIXTURES
        if not HAS_EXTRA:
            self.skipTest('requires optional js extra')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for name in ('core.js', 'duplicate.ts'):
                (root / name).write_bytes((FIXTURES / name).read_bytes())
            search = self.run_cli('symbols', root, '--query', 'core.js',
                                  '--languages', 'javascript,typescript', '--json')
            self.assertEqual(search.returncode, 0, search.stderr)
            ids = {m['id'] for m in json.loads(search.stdout)['matches']}
            self.assertTrue({'core.js::add', 'core.js::twice'} <= ids)
            context = self.run_cli('context', root, 'core.js::add',
                                   '--include-symbol', 'core.js::twice',
                                   '--languages', 'javascript,typescript', '--json')
            self.assertEqual(context.returncode, 0, context.stderr)
            self.assertIn(('core.js::twice', 'user_selected'),
                          [(b['symbol'], b['relation']) for b in json.loads(context.stdout)['blocks']])
            for target, includes in [('duplicate.ts::same', []),
                                     ('core.js::add', ['--include-symbol', 'duplicate.ts::same'])]:
                with self.subTest(target=target, includes=includes):
                    ambiguous = self.run_cli('context', root, target, *includes,
                                             '--languages', 'javascript,typescript', '--json')
                    self.assertEqual(ambiguous.returncode, 2)
                    self.assertIn('Ambiguous symbol', ambiguous.stderr)
                    self.assertEqual(ambiguous.stdout, '')
