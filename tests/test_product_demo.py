import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from repo_doctor.cli import main


class ProductDemoTests(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main(list(map(str, args)))
        return status, out.getvalue(), err.getvalue()

    def test_bundled_demo_closes_one_static_issue(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo, case_dir = base / "demo", base / "case"
            status, _, error = self.run_main("demo", "create", "--out", repo)
            self.assertEqual(status, 0, error)
            self.assertTrue((repo / "test_regression.py").exists())
            self.assertEqual(self.run_main("report", "create", repo, "--out", case_dir)[0], 0)
            case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(case["issues"][0]["id"], "S-001")
            command = [sys.executable, "-m", "unittest", "-q", "test_regression"]
            self.assertEqual(self.run_main("verify", case_dir, "S-001", "--phase", "before", "--", *command)[0], 1)
            (repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
            self.assertEqual(self.run_main("verify", case_dir, "S-001", "--phase", "after", "--", *command)[0], 0)
            self.assertEqual(self.run_main("issue", case_dir, "S-001", "--status", "resolved",
                                           "--note", "Syntax fixed and regression checked", "--related-test")[0], 0)
            self.assertIn("有修复证据", (case_dir / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
