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

    def make_v2_index(self, root: Path):
        (root / "pkg").mkdir()
        (root / "impl.py").write_text(
            "def canonical():\n    return 42\n",
            encoding="utf-8",
        )
        (root / "pkg" / "__init__.py").write_text(
            "from impl import canonical as public\n",
            encoding="utf-8",
        )
        (root / "user.py").write_text(
            "from pkg import public\n\n"
            "def use():\n"
            "    return public()\n",
            encoding="utf-8",
        )
        (root / "cli.py").write_text(
            "import click\n"
            "@click.group()\n"
            "def cli():\n"
            "    pass\n\n"
            "@cli.command()\n"
            "def leaf():\n"
            "    pass\n",
            encoding="utf-8",
        )
        return build_index(root)

    def test_context_includes_reexport_and_click_relationship_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_v2_index(Path(directory))

            canonical = build_context(index, "impl.py::canonical")
            group = build_context(index, "cli.py::cli")
            leaf = build_context(index, "cli.py::leaf")

        self.assertEqual(canonical["schema_version"], 2)
        call = next(edge for edge in canonical["call_evidence"] if edge["caller"] == "user.py::use")
        self.assertEqual(
            call["via_reexports"],
            [{"file": "pkg/__init__.py", "name": "public", "line": 1}],
        )
        self.assertTrue(
            any(
                edge["kind"] == "reexport"
                and edge["exported_name"] == "public"
                and edge["direction"] == "incoming"
                for edge in canonical["semantic_evidence"]
            )
        )

        self.assertEqual(group["schema_version"], 2)
        self.assertTrue(
            any(
                block["symbol"] == "cli.py::leaf"
                and block["relation"] == "registered_command"
                for block in group["blocks"]
            )
        )
        self.assertTrue(
            any(
                edge["kind"] == "command_registration"
                and edge["direction"] == "outgoing"
                for edge in group["semantic_evidence"]
            )
        )

        self.assertEqual(leaf["schema_version"], 2)
        self.assertTrue(
            any(
                block["symbol"] == "cli.py::cli" and block["relation"] == "registered_by"
                for block in leaf["blocks"]
            )
        )

    def test_semantic_context_neighbors_obey_source_line_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_v2_index(Path(directory))

            result = build_context(index, "cli.py::cli", max_lines=3)

        self.assertEqual([block["symbol"] for block in result["blocks"]], ["cli.py::cli"])
        self.assertTrue(result["budget_exhausted"])
        self.assertEqual(result["omitted_symbols"], 1)

    def test_impact_reports_semantic_relations_separately_from_call_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_v2_index(Path(directory))

            canonical = build_impact(index, "impl.py::canonical")
            group = build_impact(index, "cli.py::cli")
            leaf = build_impact(index, "cli.py::leaf")

        self.assertEqual(canonical["schema_version"], 2)
        self.assertTrue(
            any(
                edge["kind"] == "reexport" and edge["direction"] == "incoming"
                for edge in canonical["semantic_relations"]
            )
        )
        self.assertEqual(
            [(edge["symbol"], edge["distance"]) for edge in canonical["affected_symbols"]],
            [("user.py::use", 1)],
        )

        self.assertEqual(group["schema_version"], 2)
        self.assertEqual(group["affected_symbols"], [])
        self.assertTrue(
            any(
                edge["kind"] == "command_registration" and edge["direction"] == "outgoing"
                for edge in group["semantic_relations"]
            )
        )
        self.assertEqual(leaf["schema_version"], 2)
        self.assertTrue(
            any(
                edge["kind"] == "command_registration" and edge["direction"] == "incoming"
                for edge in leaf["semantic_relations"]
            )
        )

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
