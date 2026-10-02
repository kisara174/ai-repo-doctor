import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from repo_doctor.case import create_case, load_case, save_case, set_target
from repo_doctor.index import build_index
from repo_doctor.report import render_report


class ProductCaseTests(unittest.TestCase):
    def test_architecture_summary_uses_resolved_production_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "repo"
            repo.mkdir()
            sources = {
                "core.py": "def save(value):\n    return value\n",
                "service_one.py": "from core import save\n\ndef first(value):\n    return save(value)\n",
                "service_two.py": "from core import save\n\ndef second(value):\n    return save(value)\n",
                "api.py": "from service_one import first\n\ndef route(value):\n    return first(value)\n",
                "test_core.py": "from core import save\n\ndef test_save():\n    assert save(1) == 1\n",
            }
            for name, source in sources.items():
                (repo / name).write_text(source, encoding="utf-8")

            first = create_case(build_index(repo), base / "first")
            second = create_case(build_index(repo), base / "second")
            architecture = first["scan"]["architecture"]
            self.assertEqual(architecture, second["scan"]["architecture"])
            self.assertEqual(architecture["production_modules"], 4)
            self.assertEqual(architecture["local_import_edges"], 3)
            self.assertEqual(architecture["cross_file_call_edges"], 3)
            self.assertEqual(len(architecture["focus_modules"]), 1)
            core = architecture["focus_modules"][0]
            self.assertEqual(core["file"], "core.py")
            self.assertEqual(core["dependent_file_count"], 2)
            self.assertEqual(core["importer_count"], 2)
            self.assertEqual(core["caller_file_count"], 2)
            self.assertEqual(
                [(item["kind"], item["file"], item["line"])
                 for item in core["evidence"]],
                [("import", "service_one.py", 1), ("call", "service_one.py", 4),
                 ("import", "service_two.py", 1), ("call", "service_two.py", 4)],
            )
            self.assertNotIn("test_core.py", str(architecture))

            set_target(first, build_index(repo), "core.py::save")
            save_case(base / "first", first)
            report = (base / "first" / "report.md").read_text(encoding="utf-8")
            self.assertIn("## 静态架构摘要", report)
            self.assertIn("`core.py`", report)
            self.assertIn("`service_one.py:1`", report)
            self.assertIn("`service_one.py:4`", report)
            self.assertIn("`service_two.py:1`", report)
            self.assertIn("## 直接影响", report)
            self.assertIn("## 间接影响", report)
            self.assertIn("`api.py:4`", report)

            old_case = json.loads((base / "second" / "case.json").read_text(encoding="utf-8"))
            del old_case["scan"]["architecture"]
            (base / "second" / "case.json").write_text(json.dumps(old_case), encoding="utf-8")
            self.assertIn("# AI Repo Doctor 调查报告", render_report(load_case(base / "second")))

            solo = base / "solo"
            solo.mkdir()
            (solo / "core.py").write_text(sources["core.py"], encoding="utf-8")
            (solo / "service_one.py").write_text(sources["service_one.py"], encoding="utf-8")
            one_dependent = create_case(build_index(solo), base / "solo-case")
            self.assertEqual(one_dependent["scan"]["architecture"]["focus_modules"], [])

    def test_review_leads_have_stable_order_and_source_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / "repo"
            repo.mkdir()
            sources = {
                "broken.py": "def broken(:\n",
                "a.py": "import b\n",
                "b.py": "import a\n",
                "core.py": "def shared():\n    return 1\n\ndef local():\n    return shared()\n",
                "one.py": "from core import shared\n\ndef one():\n    return shared()\n",
                "two.py": "from core import shared\n\ndef two():\n    return shared()\n",
                "three.py": "from core import shared\n\ndef three():\n    return shared()\n",
                "test_core.py": "from core import shared\n\ndef test_shared():\n    assert shared() == 1\n",
            }
            for name, source in sources.items():
                (repo / name).write_text(source, encoding="utf-8")

            first = create_case(build_index(repo), base / "first")
            second = create_case(build_index(repo), base / "second")
            leads = first["scan"]["review_leads"]
            self.assertEqual(leads, second["scan"]["review_leads"])
            self.assertEqual([lead["kind"] for lead in leads],
                             ["parse_error", "import_cycle", "shared_call_target"])
            self.assertEqual([lead["review_order"] for lead in leads], [1, 2, 3])
            self.assertEqual(leads[0]["issue_id"], "S-001")
            self.assertEqual(leads[1]["issue_id"], "S-002")
            shared = leads[2]
            self.assertEqual(shared["subject"], "core.py::shared")
            self.assertEqual(shared["caller_count"], 3)
            self.assertEqual(
                [(item["file"], item["start_line"], item["caller"])
                 for item in shared["evidence"]],
                [("one.py", 4, "one.py::one"),
                 ("three.py", 4, "three.py::three"),
                 ("two.py", 4, "two.py::two")],
            )
            self.assertNotIn("test_core.py", str(shared))

            report = (base / "first" / "report.md").read_text(encoding="utf-8")
            self.assertIn("## 建议先检查", report)
            self.assertIn("`broken.py:1`", report)
            self.assertIn("`a.py:1`", report)
            self.assertIn("`b.py:1`", report)
            self.assertIn("`core.py::shared`", report)
            for caller_file in ("one.py", "two.py", "three.py"):
                self.assertIn(f"`{caller_file}:4`", report)
            self.assertIn("检查顺序不代表缺陷严重度", report)

            old_case = json.loads((base / "second" / "case.json").read_text(encoding="utf-8"))
            del old_case["scan"]["review_leads"]
            (base / "second" / "case.json").write_text(json.dumps(old_case), encoding="utf-8")
            self.assertNotIn("review_leads", load_case(base / "second")["scan"])
            old_case["scan"]["review_leads"] = {}
            (base / "second" / "case.json").write_text(json.dumps(old_case), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid case.json"):
                load_case(base / "second")

            solo = base / "solo"
            solo.mkdir()
            (solo / "core.py").write_text(sources["core.py"], encoding="utf-8")
            (solo / "one.py").write_text(
                "from core import shared\n\ndef one():\n    return shared()\n\ndef two():\n    return shared()\n\ndef three():\n    return shared()\n",
                encoding="utf-8",
            )
            solo_case = create_case(build_index(solo), base / "solo-case")
            self.assertFalse(any(lead["kind"] == "shared_call_target"
                                 for lead in solo_case["scan"]["review_leads"]))

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

    def test_oversize_save_preserves_both_existing_files(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / 'repo'
            repo.mkdir()
            (repo / 'app.py').write_text('def value():\n    return 1\n', encoding='utf-8')
            out = base / 'case'
            case = create_case(build_index(repo), out)
            before = {name: (out / name).read_bytes() for name in ('case.json', 'report.md')}
            case['padding'] = '中' * 5000
            with patch('repo_doctor.case.MAX_CASE_BYTES', 8192, create=True):
                with self.assertRaisesRegex(ValueError, 'exceeds'):
                    save_case(out, case)
            self.assertEqual(before, {name: (out / name).read_bytes() for name in before})
            self.assertEqual(load_case(out)['issues'], [])

    def test_case_size_boundary_counts_utf8_bytes_including_newline(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / 'repo'
            repo.mkdir()
            (repo / 'app.py').write_text('value = 1\n', encoding='utf-8')
            out = base / 'case'
            with patch('repo_doctor.case.timestamp', return_value='2026-10-02T00:00:00+00:00'):
                case = create_case(build_index(repo), out)
                case['padding'] = '中' * 100
                size = len((json.dumps(case, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
                with patch('repo_doctor.case.MAX_CASE_BYTES', size, create=True):
                    save_case(out, case)
                    self.assertEqual(load_case(out)['padding'], '中' * 100)
                original = {name: (out / name).read_bytes() for name in ('case.json', 'report.md')}
                with patch('repo_doctor.case.MAX_CASE_BYTES', size - 1, create=True):
                    with self.assertRaisesRegex(ValueError, 'exceeds'):
                        save_case(out, case)
                    with self.assertRaisesRegex(ValueError, 'exceeds'):
                        load_case(out)
                self.assertEqual(original, {name: (out / name).read_bytes() for name in original})

    def test_invalid_candidate_is_rejected_before_either_file_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = base / 'repo'
            repo.mkdir()
            (repo / 'app.py').write_text('value = 1\n', encoding='utf-8')
            out = base / 'case'
            case = create_case(build_index(repo), out)
            before = {name: (out / name).read_bytes() for name in ('case.json', 'report.md')}
            case['previews'] = 'not a list'
            with self.assertRaises(ValueError):
                save_case(out, case)
            self.assertEqual(before, {name: (out / name).read_bytes() for name in before})

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
