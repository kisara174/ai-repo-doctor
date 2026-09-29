"""User-visible, explicitly run failure evidence before AI diagnosis."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from repo_doctor.cli import main


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


if __name__ == "__main__":
    unittest.main()
