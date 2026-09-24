import json
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tests.test_diagnosis_data as data_fixture
from tools.diagnosis_data import prepare_cases
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

    def test_run_requires_allow_network_before_invoking_any_client(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("tools.evaluate_diagnosis.run_cases", create=True) as run_cases:
                code = main([
                    "run", "--plan-dir", str(root / "plan"),
                    "--manifest", str(root / "manifest.json"),
                    "--repos-root", str(root / "repos"),
                    "--out-dir", str(root / "run"),
                    "--repeats", "1", "--max-calls", "10",
                ])
            self.assertEqual(code, 2)
            run_cases.assert_not_called()
            self.assertFalse((root / "run").exists())

    def test_run_requires_environment_api_key_even_with_network_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
                with patch("tools.evaluate_diagnosis.run_cases", create=True) as run_cases:
                    code = main([
                        "run", "--plan-dir", str(root / "plan"),
                        "--manifest", str(root / "manifest.json"),
                        "--repos-root", str(root / "repos"),
                        "--out-dir", str(root / "run"),
                        "--repeats", "1", "--max-calls", "10", "--allow-network",
                    ])
            self.assertEqual(code, 2)
            run_cases.assert_not_called()
            self.assertFalse((root / "run").exists())

    def test_run_loads_prepared_files_and_passes_environment_key_to_client(self):
        fixture = data_fixture.DiagnosisDataTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(fixture.manifest), encoding="utf-8")
            with patch("tools.diagnosis_data._analyzer_commit", return_value="a" * 40):
                prepared = prepare_cases(
                    fixture.manifest, fixture.repos_root, "test-model", 120,
                    manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                )
            plan_dir = root / "plan"
            plan_dir.mkdir()
            (plan_dir / "plan.json").write_text(json.dumps(prepared["plan"]), encoding="utf-8")
            for case_id, context in prepared["contexts"].items():
                (plan_dir / f"{case_id}.json").write_text(json.dumps(context), encoding="utf-8")
            summary = {"state": "complete", "planned_calls": 1, "attempted_calls": 1}
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "TEST_SECRET_SENTINEL"}):
                with patch("tools.evaluate_diagnosis.run_cases", return_value=summary) as run_cases:
                    with patch("urllib.request.urlopen") as urlopen:
                        code = main([
                            "run", "--plan-dir", str(plan_dir),
                            "--manifest", str(manifest_path),
                            "--repos-root", str(fixture.repos_root),
                            "--out-dir", str(root / "run"), "--max-calls", "1",
                            "--allow-network",
                        ])

            self.assertEqual(code, 0)
            self.assertEqual(run_cases.call_args.kwargs["api_key"], "TEST_SECRET_SENTINEL")
            self.assertEqual(run_cases.call_args.kwargs["manifest_sha256"], hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest())
            self.assertTrue(callable(run_cases.call_args.kwargs["client"]))
            urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
