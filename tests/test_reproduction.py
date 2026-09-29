"""User-visible, explicitly run failure evidence before AI diagnosis."""

import io
import hashlib
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from repo_doctor.cli import main
from repo_doctor.deepseek import DeepSeekResult


class ReproductionTests(unittest.TestCase):
    def run_main(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(list(map(str, args)))
        return status, stdout.getvalue(), stderr.getvalue()

    def test_record_before_issue(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)

            status, output, error = self.run_main(
                "reproduce", case_dir, "--", sys.executable, "-c",
                "raise RuntimeError('observed failure')",
            )

            self.assertEqual(status, 1, error)
            self.assertIn("R-001", output)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(case["issues"], [])
            self.assertEqual(len(case["reproductions"]), 1)
            run = case["reproductions"][0]
            self.assertEqual(run["id"], "R-001")
            self.assertEqual(run["status"], "failed")
            self.assertIn("observed failure", run["output"])
            self.assertEqual(run["source_fingerprint"], run["source_fingerprint_after"])
            self.assertIn("R-001", self.run_main("report", "show", case_dir)[1])

    def test_later_pass_supersedes_failure_without_python_source_change(self):
        from repo_doctor.case import require_reproduction

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            command = [sys.executable, "-c", "import pathlib,sys; sys.exit(0 if pathlib.Path('flag').exists() else 1)"]
            self.assertEqual(self.run_main("reproduce", case_dir, "--", *command)[0], 1)
            (repo / "flag").write_text("ready", encoding="utf-8")
            self.assertEqual(self.run_main("reproduce", case_dir, "--", *command)[0], 0)

            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            fingerprint = case["reproductions"][0]["source_fingerprint"]
            with self.assertRaisesRegex(ValueError, "supersedes"):
                require_reproduction(case, "R-001", fingerprint)
            with self.assertRaisesRegex(ValueError, "failed command"):
                require_reproduction(case, "R-002", fingerprint)

    def test_selected_failure_changes_preview_but_blind_payload_stays_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            command = [sys.executable, "-c", "import app; assert app.target() == 2"]
            self.assertEqual(self.run_main("reproduce", case_dir, "--", *command)[0], 1)

            blind = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir, "--preview")
            selected = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir,
                                     "--reproduction", "R-001", "--preview")

            self.assertEqual(blind[0], 0, blind[2])
            self.assertEqual(hashlib.sha256(blind[1].encode()).hexdigest(),
                             "2d1d7ca4b298c17d511d01dc6e70e8bad41d7120cbec1844540959862bf3fd12")
            self.assertEqual(selected[0], 0, selected[2])
            self.assertNotEqual(blind[1], selected[1])
            body = json.loads(selected[1])
            observation = json.loads(body["messages"][1]["content"])["reproduction"]
            self.assertEqual(observation["id"], "R-001")
            self.assertEqual(observation["argv"], command)
            self.assertEqual(observation["exit_code"], 1)
            self.assertIn("AssertionError", observation["output"])
            self.assertIn("untrusted observation", body["messages"][0]["content"])
            self.assertIn(hashlib.sha256(selected[1].encode()).hexdigest(), selected[2])
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertNotIn("reproduction_id", case["previews"][0])
            self.assertEqual(case["previews"][1]["reproduction_id"], "R-001")

    def test_selected_failure_preview_bytes_match_live_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            self.assertEqual(self.run_main("reproduce", case_dir, "--", sys.executable, "-c", "raise RuntimeError('observed')")[0], 1)
            for format_args in ((), ("--response-format", "json-schema")):
                with self.subTest(format_args=format_args):
                    preview = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir,
                                            "--reproduction", "R-001", *format_args, "--preview")
                    self.assertEqual(preview[0], 0, preview[2])
                    payload = []

                    def transport(request, timeout):
                        payload.append(request.data)
                        if format_args:
                            envelope = {"object": "response", "status": "completed", "model": "deepseek-flash",
                                        "output": [{"type": "message", "role": "assistant", "content": [
                                            {"type": "output_text", "text": '{"findings": []}'},
                                        ]}]}
                        else:
                            envelope = {"model": "deepseek-flash", "choices": [{"finish_reason": "stop",
                                        "message": {"content": '{"findings": []}'}}]}
                        return json.dumps(envelope).encode()

                    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                        "repo_doctor.deepseek._read_response", side_effect=transport
                    ):
                        live = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir,
                                             "--reproduction", "R-001", *format_args,
                                             "--expect-request-sha256", hashlib.sha256(preview[1].encode()).hexdigest())
                    self.assertEqual(live[0], 0, live[2])
                    self.assertEqual(payload, [preview[1].encode()])
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual([item["reproduction_id"] for item in case["diagnoses"]], ["R-001", "R-001"])

    def test_stale_or_unpreviewed_reproduction_blocks_network(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            self.assertEqual(self.run_main("reproduce", case_dir, "--", sys.executable, "-c", "raise RuntimeError('observed')")[0], 1)
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json"
            ) as client:
                missing_hash = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir,
                                             "--reproduction", "R-001")
                self.assertEqual(missing_hash[0], 2)
                self.assertIn("--expect-request-sha256", missing_hash[2])
                client.assert_not_called()
                (repo / "app.py").write_text("def target():\n    return 2\n", encoding="utf-8")
                stale = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir,
                                      "--reproduction", "R-001", "--preview")
                self.assertEqual(stale[0], 2)
                self.assertIn("source changed", stale[2].lower())
                client.assert_not_called()
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(case["diagnoses"], [])

    def test_unselected_python_source_change_during_provider_discards_response(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
            (repo / "other.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            self.assertEqual(self.run_main("reproduce", case_dir, "--", sys.executable, "-c", "raise RuntimeError('observed')")[0], 1)
            preview = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir,
                                    "--reproduction", "R-001", "--preview")
            self.assertEqual(preview[0], 0, preview[2])

            def change_other_source(*args, **kwargs):
                (repo / "other.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
                return DeepSeekResult("deepseek-flash", {"findings": []})

            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json", side_effect=change_other_source
            ):
                status, output, error = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir,
                                                      "--reproduction", "R-001",
                                                      "--expect-request-sha256", hashlib.sha256(preview[1].encode()).hexdigest())
            self.assertEqual(status, 2, error)
            self.assertEqual(output, "")
            self.assertIn("source changed", error.lower())
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(case["issues"], [])
            self.assertEqual(case["diagnoses"][-1]["status"], "source_changed")
            self.assertEqual(case["diagnoses"][-1]["reproduction_id"], "R-001")

    def test_reproduction_link_closes_only_after_same_command_and_human_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            command = [sys.executable, "-c", "import app; assert app.value() == 2"]
            self.assertEqual(self.run_main("reproduce", case_dir, "--", *command)[0], 1)
            preview = self.run_main("diagnose", repo, "app.py::value", "--case", case_dir,
                                    "--reproduction", "R-001", "--preview")
            self.assertEqual(preview[0], 0, preview[2])
            finding = {
                "title": "Wrong return value", "category": "behavior", "confidence": 0.8,
                "reasoning": "The observed assertion expects two, but this function returns one.",
                "impact": "The selected check fails.", "suggested_fix": "Review the intended return value.",
                "evidence": [{"file": "app.py", "start_line": 2, "end_line": 2,
                              "quote": "    return 1", "symbol": "app.py::value"}],
            }
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret"}, clear=True), patch(
                "repo_doctor.cli.complete_json",
                return_value=DeepSeekResult("deepseek-flash", {"findings": [finding]}),
            ):
                live = self.run_main("diagnose", repo, "app.py::value", "--case", case_dir,
                                     "--reproduction", "R-001", "--expect-request-sha256",
                                     hashlib.sha256(preview[1].encode()).hexdigest())
            self.assertEqual(live[0], 0, live[2])
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            issue = case["issues"][0]
            self.assertEqual(issue["id"], "A-001")
            self.assertEqual(issue["human_status"], "unreviewed")
            self.assertEqual(issue["reproduction_id"], "R-001")
            self.assertEqual(issue["verification"][0]["phase"], "before")
            self.assertEqual(issue["verification"][0]["argv"], command)
            self.assertNotIn("output", issue["verification"][0])
            self.assertIn("仍需复核", self.run_main("report", "show", case_dir)[1])

            (repo / "app.py").write_text("def value():\n    return 2\n", encoding="utf-8")
            self.assertEqual(self.run_main("verify", case_dir, "A-001", "--phase", "after",
                                           "--", *command)[0], 0)
            self.assertIn("仍需复核", self.run_main("report", "show", case_dir)[1])
            self.assertEqual(self.run_main("issue", case_dir, "A-001", "--status", "resolved",
                                           "--note", "I confirm this check covers the finding",
                                           "--related-test")[0], 0)
            report = self.run_main("report", "show", case_dir)[1]
            self.assertIn("有修复证据", report)
            self.assertIn("R-001", report)
            self.assertIn("AI 假设", report)

    def test_existing_schema_one_case_without_reproductions_can_be_reopened(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            path = case_dir / "case.json"
            old_case = json.loads(path.read_text(encoding="utf-8"))
            old_case.pop("reproductions")
            path.write_text(json.dumps(old_case), encoding="utf-8")

            reopened = self.run_main("report", "show", case_dir)
            self.assertEqual(reopened[0], 0, reopened[2])
            self.assertIn("尚无显式复现记录", reopened[1])
            self.assertEqual(self.run_main("reproduce", case_dir, "--", sys.executable, "-c",
                                           "raise RuntimeError('observed')")[0], 1)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema_version"], 1)
            self.assertEqual(saved["reproductions"][0]["id"], "R-001")

    def test_command_that_mutated_python_source_cannot_be_used_even_after_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            original = "def target():\n    return 1\n"
            (repo / "app.py").write_text(original, encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            script = "from pathlib import Path; Path('app.py').write_text('def target():\\n    return 2\\n'); raise RuntimeError('failed')"
            self.assertEqual(self.run_main("reproduce", case_dir, "--", sys.executable, "-c", script)[0], 1)
            (repo / "app.py").write_text(original, encoding="utf-8")

            status, output, error = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir,
                                                  "--reproduction", "R-001", "--preview")
            self.assertEqual(status, 2)
            self.assertEqual(output, "")
            self.assertIn("during execution", error)

    def test_truncated_failure_output_requires_narrower_reproduction(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "repo", base / "case"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            script = "print('log' * 10000); raise RuntimeError('actual failure at end')"
            self.assertEqual(self.run_main("reproduce", case_dir, "--", sys.executable, "-c", script)[0], 1)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertTrue(case["reproductions"][0]["output_truncated"])

            status, output, error = self.run_main("diagnose", repo, "app.py::target", "--case", case_dir,
                                                  "--reproduction", "R-001", "--preview")
            self.assertEqual(status, 2)
            self.assertEqual(output, "")
            self.assertIn("output was truncated", error)


if __name__ == "__main__":
    unittest.main()
