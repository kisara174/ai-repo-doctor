import tempfile
import unittest
from pathlib import Path

from repo_doctor.context import build_context, build_impact
from repo_doctor.index import build_index


class ContextTests(unittest.TestCase):
    def make_index(self, root: Path):
        (root / "helpers.py").write_text("def save(value):\n    return value\n", encoding="utf-8")
        (root / "service.py").write_text(
            "from helpers import save\n\ndef process(value):\n    return save(value)\n",
            encoding="utf-8",
        )
        (root / "api.py").write_text(
            "from service import process\n\ndef route(value):\n    return process(value)\n",
            encoding="utf-8",
        )
        (root / "tests").mkdir()
        (root / "tests" / "test_service.py").write_text(
            "from service import process\n\ndef test_process():\n    assert process(1) == 1\n",
            encoding="utf-8",
        )
        return build_index(root)

    def test_context_orders_target_callee_caller_and_related_test(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_index(Path(directory))

            result = build_context(index, "service.py::process", max_lines=20)

        self.assertEqual(
            [(block["symbol"], block["relation"]) for block in result["blocks"]],
            [
                ("service.py::process", "target"),
                ("helpers.py::save", "callee"),
                ("api.py::route", "caller"),
                ("tests/test_service.py::test_process", "related_test"),
            ],
        )
        self.assertEqual(result["blocks"][0]["lines"][0], {"line": 3, "text": "def process(value):"})
        self.assertEqual(result["blocks"][0]["lines"][1], {"line": 4, "text": "    return save(value)"})

    def test_context_marks_truncation_and_respects_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_index(Path(directory))

            result = build_context(index, "service.py::process", max_lines=1)

        self.assertEqual(len(result["blocks"]), 1)
        self.assertEqual(result["blocks"][0]["lines"], [{"line": 3, "text": "def process(value):"}])
        self.assertTrue(result["blocks"][0]["truncated"])
        self.assertTrue(result["budget_exhausted"])

    def test_impact_follows_reverse_calls_to_requested_depth(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_index(Path(directory))

            result = build_impact(index, "helpers.py::save", depth=2)

        self.assertEqual(
            [(item["symbol"], item["distance"]) for item in result["affected_symbols"]],
            [
                ("service.py::process", 1),
                ("api.py::route", 2),
                ("tests/test_service.py::test_process", 2),
            ],
        )
        self.assertEqual(result["module_importers"], ["service.py"])

    def test_unknown_symbol_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_index(Path(directory))

            with self.assertRaisesRegex(ValueError, "Unknown symbol"):
                build_context(index, "missing.py::unknown", max_lines=20)

    def test_context_rejects_source_replaced_by_outside_symlink(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            index = self.make_index(root)
            (root / "service.py").unlink()
            (Path(outside) / "service.py").write_text(
                "def process(value):\n    return 'outside source'\n", encoding="utf-8"
            )
            (root / "service.py").symlink_to(Path(outside) / "service.py")

            with self.assertRaisesRegex(ValueError, "Unsafe"):
                build_context(index, "service.py::process", max_lines=20)

    def test_context_rejects_repository_root_replaced_by_symlink(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            parent = Path(directory)
            root = parent / "repo"
            root.mkdir()
            index = self.make_index(root)
            root.rename(parent / "moved")
            (Path(outside) / "service.py").write_text(
                "x = 1\ny = 2\ndef process(value):\n    return 'outside source'\n", encoding="utf-8"
            )
            root.symlink_to(Path(outside), target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "Unsafe"):
                build_context(index, "service.py::process", max_lines=1)

    def test_context_rejects_parent_directory_replaced_by_symlink(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            base = Path(directory)
            parent = base / "parent"
            root = parent / "repo"
            root.mkdir(parents=True)
            index = self.make_index(root)
            parent.rename(base / "moved")
            outside_root = Path(outside) / "repo"
            outside_root.mkdir()
            (outside_root / "service.py").write_text(
                "x = 1\ny = 2\ndef process(value):\n    return 'outside source'\n", encoding="utf-8"
            )
            parent.symlink_to(Path(outside), target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "Unsafe"):
                build_context(index, "service.py::process", max_lines=1)

    def test_context_rejects_repository_replaced_by_new_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repo"
            root.mkdir()
            index = self.make_index(root)
            root.rename(base / "old-repo")
            root.mkdir()
            (root / "service.py").write_text(
                "x = 1\ny = 2\ndef process(value):\n    return 'different source'\n", encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "Unsafe"):
                build_context(index, "service.py::process", max_lines=1)
