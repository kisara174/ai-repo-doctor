import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from repo_doctor.cli import main
from repo_doctor.deepseek import DeepSeekResult


class ProductVerifyTests(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main(list(map(str, args)))
        return status, out.getvalue(), err.getvalue()

    def make_case_with_issue(self, base):
        repo, case_dir = base / "repo", base / "case"
        repo.mkdir()
        (repo / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
        self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
        finding = {
            "title": "Wrong value", "category": "reliability", "confidence": 0.8,
            "reasoning": "Expected two.", "impact": "Caller gets one.",
            "suggested_fix": "Return two.",
            "evidence": [{"file": "app.py", "start_line": 2, "end_line": 2,
                          "quote": "    return 1", "symbol": "app.py::value"}],
        }
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
            "repo_doctor.cli.complete_json", return_value=DeepSeekResult("model", {"findings": [finding]})
        ):
            self.assertEqual(self.run_main("diagnose", repo, "app.py::value", "--case", case_dir)[0], 0)
        return repo, case_dir

    def test_before_after_same_command_requires_source_change_and_human_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, case_dir = self.make_case_with_issue(Path(directory))
            command = [sys.executable, "-c", "import app; assert app.value() == 2"]
            before = self.run_main("verify", case_dir, "A-001", "--phase", "before", "--", *command)
            self.assertEqual(before[0], 1, before[2])
            (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
            after = self.run_main("verify", case_dir, "A-001", "--phase", "after", "--", *command)
            self.assertEqual(after[0], 0, after[2])
            self.assertIn("仍需复核", (case_dir / "report.md").read_text(encoding="utf-8"))
            self.assertEqual(self.run_main("issue", case_dir, "A-001", "--status", "resolved",
                                           "--note", "Confirmed this regression checks the value",
                                           "--related-test")[0], 0)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            records = case["issues"][0]["verification"]
            self.assertEqual([item["status"] for item in records], ["failed", "passed"])
            self.assertEqual(records[0]["argv"], records[1]["argv"])
            self.assertNotEqual(records[0]["source_fingerprint"], records[1]["source_fingerprint"])
            self.assertIn("有修复证据", (case_dir / "report.md").read_text(encoding="utf-8"))
            status, output, error = self.run_main("issue", case_dir, "A-001")
            self.assertEqual(status, 0, error)
            self.assertIn("有修复证据", output)

    def test_verify_strips_key_caps_output_and_does_not_pair_different_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, case_dir = self.make_case_with_issue(Path(directory))
            command = [sys.executable, "-c", "import os; assert 'DEEPSEEK_API_KEY' not in os.environ; print('x'*100000)"]
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}):
                status, output, error = self.run_main("verify", case_dir, "A-001", "--phase", "before", "--", *command)
            self.assertEqual(status, 0, error)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            record = case["issues"][0]["verification"][0]
            self.assertLessEqual(len(record["output"].encode("utf-8")), 16384)
            self.assertTrue(record["output_truncated"])
            (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "after", "--",
                                           sys.executable, "-c", "import app; assert app.value() == 2")[0], 0)
            self.assertEqual(self.run_main("issue", case_dir, "A-001", "--status", "resolved",
                                           "--note", "Related", "--related-test")[0], 0)
            self.assertIn("仍需复核", (case_dir / "report.md").read_text(encoding="utf-8"))

    def test_timeout_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            _, case_dir = self.make_case_with_issue(Path(directory))
            for script in (
                "import time; time.sleep(5)",
                "import os, time; os.close(1); os.close(2); time.sleep(5)",
            ):
                with self.subTest(script=script):
                    status, _, error = self.run_main("verify", case_dir, "A-001", "--phase", "before",
                                                     "--timeout", "1", "--", sys.executable, "-c", script)
                    self.assertEqual(status, 1, error)
                    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
                    self.assertEqual(case["issues"][0]["verification"][-1]["status"], "timeout")

    def test_non_source_change_cannot_be_claimed_as_fix(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, case_dir = self.make_case_with_issue(Path(directory))
            command = [sys.executable, "-c", "from pathlib import Path; assert Path('flag').exists()"]
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "before", "--", *command)[0], 1)
            (repo / "flag").write_text("enabled", encoding="utf-8")
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "after", "--", *command)[0], 0)
            self.assertEqual(self.run_main("issue", case_dir, "A-001", "--status", "resolved",
                                           "--note", "Claimed fix", "--related-test")[0], 0)
            report = (case_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("仍需复核", report)
            self.assertNotIn("有修复证据", report)

    def test_command_that_mutates_source_cannot_be_claimed_as_fix(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, case_dir = self.make_case_with_issue(Path(directory))
            script = (
                "import app; assert app.value() == 2; "
                "from pathlib import Path; "
                "Path('app.py').write_text('def value():\\n    return 3\\n')"
            )
            command = [sys.executable, "-c", script]
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "before", "--", *command)[0], 1)
            (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "after", "--", *command)[0], 0)
            self.assertEqual(self.run_main("issue", case_dir, "A-001", "--status", "resolved",
                                           "--note", "Claimed fix", "--related-test")[0], 0)
            self.assertNotIn("有修复证据", (case_dir / "report.md").read_text(encoding="utf-8"))

    def test_after_run_cannot_pair_with_later_before_run(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, case_dir = self.make_case_with_issue(Path(directory))
            command = [sys.executable, "-c", "import app; assert app.value() == 2"]
            (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "after", "--", *command)[0], 0)
            (repo / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "before", "--", *command)[0], 1)
            self.assertEqual(self.run_main("issue", case_dir, "A-001", "--status", "resolved",
                                           "--note", "Claimed fix", "--related-test")[0], 0)
            self.assertNotIn("有修复证据", (case_dir / "report.md").read_text(encoding="utf-8"))

    def test_invalid_utf8_output_still_respects_saved_byte_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            _, case_dir = self.make_case_with_issue(Path(directory))
            command = [sys.executable, "-c", "import os; os.write(1, bytes([255]) * 30000)"]
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "before", "--", *command)[0], 0)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            output = case["issues"][0]["verification"][0]["output"]
            self.assertLessEqual(len(output.encode("utf-8")), 16384)

    def test_background_child_holding_output_cannot_mark_run_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            _, case_dir = self.make_case_with_issue(Path(directory))
            script = (
                "import subprocess, sys; "
                "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3)']); "
                "print('parent done')"
            )
            status, _, error = self.run_main("verify", case_dir, "A-001", "--phase", "before",
                                             "--timeout", "1", "--", sys.executable, "-c", script)
            self.assertEqual(status, 1, error)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(case["issues"][0]["verification"][0]["status"], "timeout")

    @unittest.skipUnless(os.name == "posix", "detached process sessions require POSIX")
    def test_detached_child_holding_output_does_not_block_timeout_return(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, case_dir = self.make_case_with_issue(Path(directory))
            script = (
                "import subprocess, sys; from pathlib import Path; "
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], "
                "start_new_session=True); Path('child.pid').write_text(str(child.pid)); "
                "print('parent done', flush=True)"
            )
            started = time.monotonic()
            try:
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "repo_doctor", "verify", str(case_dir),
                         "A-001", "--phase", "before", "--timeout", "1", "--",
                         sys.executable, "-c", script],
                        cwd=Path(__file__).resolve().parents[1],
                        capture_output=True, text=True, timeout=4,
                    )
                except subprocess.TimeoutExpired:
                    self.fail("verification kept waiting for a detached child's output after timeout")
                self.assertLess(time.monotonic() - started, 3)
                self.assertEqual(result.returncode, 1, result.stderr)
                case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
                record = case["issues"][0]["verification"][0]
                self.assertEqual(record["status"], "timeout")
                self.assertIn("parent done", record["output"])
            finally:
                pid_path = repo / "child.pid"
                if pid_path.exists():
                    try:
                        os.kill(int(pid_path.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_new_before_run_requires_an_after_run_for_new_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, case_dir = self.make_case_with_issue(Path(directory))
            command = [sys.executable, "-c", "import app; assert app.value() == 2"]
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "before", "--", *command)[0], 1)
            (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "after", "--", *command)[0], 0)
            self.assertEqual(self.run_main("issue", case_dir, "A-001", "--status", "resolved",
                                           "--note", "This check covers the issue", "--related-test")[0], 0)
            self.assertIn("有修复证据", self.run_main("report", "show", case_dir)[1])

            (repo / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "before", "--", *command)[0], 1)
            reopened = self.run_main("report", "show", case_dir)
            self.assertEqual(reopened[0], 0, reopened[2])
            self.assertIn("仍需复核", reopened[1])
            self.assertNotIn("有修复证据", reopened[1])

            (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "after", "--", *command)[0], 0)
            self.assertIn("有修复证据", self.run_main("report", "show", case_dir)[1])


if __name__ == "__main__":
    unittest.main()
