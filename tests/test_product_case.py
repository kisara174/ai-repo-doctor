import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from repo_doctor.case import create_case, load_case, save_case, set_target
from repo_doctor.index import build_index


class ProductCaseTests(unittest.TestCase):
    def test_create_reopen_and_render_static_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "repo"
            repo.mkdir()
            (repo / "app.py").write_text("def target():\n    return 1\n", encoding="utf-8")
            (repo / "broken.py").write_text("def broken(:\n", encoding="utf-8")
            case_dir = base / "case"
            index = build_index(repo)

            case = create_case(index, case_dir)
            reopened = load_case(case_dir)

            self.assertEqual(case, reopened)
            self.assertEqual(case["schema_version"], 1)
            self.assertEqual(case["repository"]["root"], str(repo.resolve()))
            self.assertEqual(case["scan"]["stats"]["python_files"], 2)
            self.assertEqual(case["scan"]["parse_errors"][0]["file"], "broken.py")
            self.assertEqual(case["issues"][0]["id"], "S-001")
            self.assertEqual(case["issues"][0]["origin"], "static")
            self.assertIn("broken.py", (case_dir / "report.md").read_text(encoding="utf-8"))
            self.assertEqual(stat.S_IMODE((case_dir / "case.json").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((case_dir / "report.md").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(case_dir.stat().st_mode), 0o700)

            set_target(case, index, "app.py::target")
            save_case(case_dir, case)
            reopened = load_case(case_dir)
            self.assertEqual(reopened["target"]["symbol"], "app.py::target")
            self.assertEqual(reopened["target"]["impact"]["affected_symbols"], [])
            self.assertEqual(reopened["issues"][0]["id"], "S-001")

    def test_create_refuses_to_replace_existing_case(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "repo"
            repo.mkdir()
            (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
            case_dir = base / "case"
            create_case(build_index(repo), case_dir)
            original = (case_dir / "case.json").read_bytes()

            with self.assertRaisesRegex(ValueError, "already exists"):
                create_case(build_index(repo), case_dir)

            self.assertEqual((case_dir / "case.json").read_bytes(), original)

    def test_save_preserves_existing_report_when_case_json_is_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "repo"
            repo.mkdir()
            (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
            case_dir = base / "case"
            case = create_case(build_index(repo), case_dir)
            external = base / "external.json"
            external.write_text("untouched", encoding="utf-8")
            (case_dir / "case.json").unlink()
            (case_dir / "case.json").symlink_to(external)

            with self.assertRaisesRegex(ValueError, "symlink"):
                save_case(case_dir, case)

            self.assertEqual(external.read_text(encoding="utf-8"), "untouched")

    def test_malformed_case_returns_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "repo"
            repo.mkdir()
            (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
            case_dir = base / "case"
            create_case(build_index(repo), case_dir)
            (case_dir / "case.json").write_text('{"schema_version": 1, "repository": {"root": 1}, "issues": []}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "invalid case.json"):
                load_case(case_dir)

    def test_report_keeps_code_paths_copyable(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "repo"
            repo.mkdir()
            (repo / "my_module.py").write_text("def my_function():\n    return 1\n", encoding="utf-8")
            case_dir = base / "case"
            case = create_case(build_index(repo), case_dir)
            set_target(case, build_index(repo), "my_module.py::my_function")
            save_case(case_dir, case)

            report = (case_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("`my_module.py::my_function`", report)
            self.assertNotIn("my\\_module", report)


if __name__ == "__main__":
    unittest.main()
