import io
import json
import os
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from repo_doctor.cli import main
from repo_doctor.deepseek import DeepSeekError, DeepSeekResult


class ProductCliTests(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main(list(map(str, args)))
        return status, out.getvalue(), err.getvalue()

    def test_version_does_not_scan_or_require_a_repository(self):
        out = io.StringIO()
        with redirect_stdout(out), patch('repo_doctor.cli.build_index', side_effect=AssertionError('must not scan')):
            with self.assertRaises(SystemExit) as result:
                main(['--version'])
        self.assertEqual(result.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), 'repo-doctor 0.6.0a1')

    def test_new_report_version_matches_release_and_old_case_stays_original(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / 'repo', base / 'case'
            repo.mkdir()
            (repo / 'app.py').write_text('value = 1\n', encoding='utf-8')
            status, output, error = self.run_main('report', 'create', repo, '--out', case_dir, '--json')
            self.assertEqual(status, 0, error)
            case = json.loads(output)
            self.assertEqual(case['tool_version'], '0.6.0a1')
            case['tool_version'] = '0.5.0'
            (case_dir / 'case.json').write_text(json.dumps(case), encoding='utf-8')
            before = {name: (case_dir / name).read_bytes() for name in ('case.json', 'report.md')}
            status, output, error = self.run_main('report', 'show', case_dir, '--json')
            self.assertEqual(status, 0, error)
            self.assertEqual(json.loads(output)['tool_version'], '0.5.0')
            self.assertEqual(before, {name: (case_dir / name).read_bytes() for name in before})

    def test_create_show_and_symbol_search_are_reopenable(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "investigation"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")

            status, output, error = self.run_main("report", "create", repo, "--out", case_dir,
                                                   "--symbol", "app.py::target")
            self.assertEqual(status, 0, error)
            self.assertIn(str(case_dir), output)
            status, output, error = self.run_main("report", "show", case_dir)
            self.assertEqual(status, 0, error)
            self.assertIn("app.py::target", output)
            self.assertIn("尚未发起云端诊断", output)
            status, output, error = self.run_main("symbols", repo, "--query", "target", "--json")
            self.assertEqual(status, 0, error)
            self.assertEqual(json.loads(output)["matches"][0]["id"], "app.py::target")
            status, output, error = self.run_main("symbols", repo, "--query", "targte")
            self.assertEqual(status, 0, error)
            self.assertIn("Candidates", output)
            self.assertIn("app.py::target", output)

    def test_import_that_exceeds_case_capacity_keeps_previous_task_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / 'repo', base / 'case'
            repo.mkdir()
            (repo / 'app.py').write_text('def target():\n    return 2\n', encoding='utf-8')
            self.assertEqual(self.run_main('report', 'create', repo, '--out', case_dir)[0], 0)
            snapshot = base / 'context.json'
            self.assertEqual(self.run_main('context', repo, 'app.py::target', '--snapshot-out', snapshot)[0], 0)
            finding = dict(title='Bounded input', category='behavior', confidence=0.5,
                           reasoning='r' * 800000, impact='Candidate only', suggested_fix='Review',
                           evidence=[dict(file='app.py', start_line=2, end_line=2, quote='return 2')])
            payload = base / 'findings.json'
            payload.write_text(json.dumps({'findings': [finding]}), encoding='utf-8')
            self.assertLess(payload.stat().st_size, 1024 * 1024)
            argv = ['findings', 'import', case_dir, '--from', payload, '--context', snapshot,
                    '--producer', 'codex', '--json']
            for _ in range(5):
                self.assertEqual(self.run_main(*argv)[0], 0)
            original = {name: (case_dir / name).read_bytes() for name in ('case.json', 'report.md')}
            status, _, error = self.run_main(*argv)
            self.assertEqual(status, 2, error)
            self.assertIn('exceeds 8 MiB', error)
            self.assertEqual(original, {name: (case_dir / name).read_bytes() for name in original})
            status, output, error = self.run_main('report', 'show', case_dir, '--json')
            self.assertEqual(status, 0, error)
            self.assertEqual(len(json.loads(output)['issues']), 5)

    def test_diagnosis_creates_stable_issue_and_preserves_human_judgment(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            finding = {
                "title": "Possible wrong return", "category": "reliability", "confidence": 0.7,
                "reasoning": "This return may not match callers.", "impact": "Callers get one.",
                "suggested_fix": "Check the expected value.",
                "evidence": [{"file": "app.py", "start_line": 2, "end_line": 2,
                              "quote": "    return 1", "symbol": "app.py::target"}],
            }
            response = DeepSeekResult("deepseek-flash", {"findings": [finding]})
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json", return_value=response
            ):
                status, output, error = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir)
            self.assertEqual(status, 0, error)
            self.assertIn("Possible wrong return", output)
            self.assertIn("app.py:2", output)
            self.assertIn("This return may not match callers.", output)
            self.assertIn("Check the expected value.", output)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(case["diagnoses"][0]["status"], "accepted")
            self.assertEqual(case["issues"][0]["id"], "A-001")
            self.assertEqual(case["issues"][0]["finding"], finding)
            self.assertIn("Possible wrong return", (case_dir / "report.md").read_text(encoding="utf-8"))

            status, _, error = self.run_main("issue", case_dir, "A-001", "--status", "rejected",
                                              "--note", "Callers actually require one")
            self.assertEqual(status, 0, error)
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json", return_value=response
            ):
                self.assertEqual(self.run_main("diagnose", repo, "app.py::target", "--case", case_dir)[0], 0)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in case["issues"]], ["A-001", "A-002"])
            self.assertEqual(case["issues"][0]["human_status"], "rejected")
            self.assertEqual(case["issues"][0]["human_history"][0]["note"], "Callers actually require one")

    def test_empty_rejected_and_provider_failure_have_distinct_case_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            invalid_finding = {
                "title": "Bad quote", "category": "reliability", "confidence": 0.8,
                "reasoning": "Maybe wrong", "impact": "Maybe impact", "suggested_fix": "Review",
                "evidence": [{"file": "app.py", "start_line": 2, "end_line": 2, "quote": "invented"}],
            }
            outcomes = [
                (DeepSeekResult("model", {"findings": []}), 0, "empty"),
                (DeepSeekResult("model", {"findings": [invalid_finding]}), 1, "rejected"),
                (DeepSeekError("invalid JSON", code="invalid_response", error_detail="invalid_content_json"), 2, "invalid_json"),
                (DeepSeekError("invalid shape", code="invalid_response", error_detail="invalid_content_shape"), 2, "invalid_response"),
                (DeepSeekError("connection failed", code="connection"), 2, "connection_failure"),
                (DeepSeekError("balance", code="http", http_status=402), 2, "provider_failure"),
            ]
            for response, expected_exit, expected_status in outcomes:
                with self.subTest(expected_status=expected_status):
                    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                        "repo_doctor.cli.complete_json",
                        side_effect=response if isinstance(response, Exception) else None,
                        return_value=None if isinstance(response, Exception) else response,
                    ):
                        status, _, _ = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir)
                    self.assertEqual(status, expected_exit)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual([item["status"] for item in case["diagnoses"]],
                             ["empty", "rejected", "invalid_json", "invalid_response", "connection_failure", "provider_failure"])
            self.assertEqual(case["diagnoses"][-1]["error_category"], "balance")
            self.assertEqual(case["issues"], [])
            self.assertNotIn("test-secret", (case_dir / "report.md").read_text(encoding="utf-8"))

    def test_preview_records_request_hash_without_calling_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            with patch("repo_doctor.cli.complete_json") as client:
                status, _, error = self.run_main("diagnose", repo, "app.py::target", "--preview",
                                                  "--case", case_dir)
            self.assertEqual(status, 0, error)
            client.assert_not_called()
            hash_in_stderr = re.search(r"SHA-256: ([0-9a-f]{64})", error).group(1)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(case["previews"][0]["request_sha256"], hash_in_stderr)
            self.assertEqual(case["diagnoses"], [])

    def test_report_create_explains_empty_scan_caused_by_parent_git_ignore(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            subprocess.run(["git", "init", "-q", str(parent)], check=True)
            (parent / ".gitignore").write_text("scratch/\n", encoding="utf-8")
            repo = parent / "scratch" / "repo"
            repo.mkdir(parents=True)
            (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
            case_dir = parent / "case"

            status, _, error = self.run_main("report", "create", repo, "--out", case_dir)

            self.assertEqual(status, 2)
            self.assertIn("Git ignore", error)
            self.assertFalse(case_dir.exists())


if __name__ == "__main__":
    unittest.main()
