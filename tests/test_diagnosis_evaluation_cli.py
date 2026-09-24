import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tests.test_diagnosis_data as data_fixture
from tools.evaluate_diagnosis import main


class DiagnosisEvaluationCliTests(unittest.TestCase):
    def test_prepare_atomically_writes_plan_and_context(self):
        fixture = data_fixture.DiagnosisDataTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(fixture.manifest), encoding="utf-8")
            output = root / "prepared"
            with patch("tools.diagnosis_data._analyzer_commit", return_value="a" * 40):
                code = main([
                    "prepare", "--manifest", str(manifest_path),
                    "--repos-root", str(fixture.repos_root), "--model", "test-model",
                    "--out-dir", str(output),
                ])

            self.assertEqual(code, 0)
            plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
            context = json.loads((output / "bug-01.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["manifest_sha256"], hashlib.sha256(manifest_path.read_bytes()).hexdigest())
            self.assertEqual(plan["analyzer_commit"], "a" * 40)
            self.assertEqual(context["symbol"], "app.py::broken")
            self.assertEqual(set(context), {"symbol", "blocks", "call_evidence"})

    def test_prepare_refuses_an_existing_output_directory(self):
        fixture = data_fixture.DiagnosisDataTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(fixture.manifest), encoding="utf-8")
            output = root / "prepared"
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")
            code = main([
                "prepare", "--manifest", str(manifest_path),
                "--repos-root", str(fixture.repos_root), "--model", "test-model",
                "--out-dir", str(output),
            ])
            self.assertEqual(code, 2)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertFalse((output / "plan.json").exists())

    def test_prepare_rejects_an_empty_model_before_writing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "prepared"
            code = main([
                "prepare", "--manifest", str(root / "missing.json"),
                "--repos-root", str(root), "--model", "", "--out-dir", str(output),
            ])
            self.assertEqual(code, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
