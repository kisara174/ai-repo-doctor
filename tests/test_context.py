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
                ("api.py::<module import process>", "import_binding"),
                ("service.py::<module import save>", "import_binding"),
                ("tests/test_service.py::<module import process>", "import_binding"),
            ],
        )
        self.assertEqual(result["blocks"][0]["lines"][0], {"line": 3, "text": "def process(value):"})
        self.assertEqual(result["blocks"][0]["lines"][1], {"line": 4, "text": "    return save(value)"})

    def test_context_includes_local_base_chain_and_used_import_with_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "errors.py").write_text(
                "from compat import Decoder\n"
                "from compat import unrelated\n"
                "\n"
                "class GrandError(Exception): pass\n"
                "class BaseError(GrandError): pass\n"
                "class ChildError(BaseError):\n"
                "    def decode(self):\n"
                "        return Decoder()\n",
                encoding="utf-8",
            )
            index = build_index(root)

            six_lines = build_context(index, "errors.py::ChildError", max_lines=6)
            five_lines = build_context(index, "errors.py::ChildError", max_lines=5)

        self.assertEqual(
            [(block["symbol"], block["relation"]) for block in six_lines["blocks"][:3]],
            [
                ("errors.py::ChildError", "target"),
                ("errors.py::BaseError", "base_class"),
                ("errors.py::GrandError", "base_class"),
            ],
        )
        self.assertTrue(
            any(
                block["relation"] == "import_binding"
                and any(line["text"] == "from compat import Decoder" for line in block["lines"])
                for block in six_lines["blocks"]
            )
        )
        self.assertFalse(
            any(
                line["text"] == "from compat import unrelated"
                for block in six_lines["blocks"]
                for line in block["lines"]
            )
        )
        self.assertEqual(sum(len(block["lines"]) for block in six_lines["blocks"]), 6)
        self.assertEqual(six_lines["omitted_imports"], 0)

        self.assertLessEqual(sum(len(block["lines"]) for block in five_lines["blocks"]), 5)
        self.assertEqual(five_lines["omitted_imports"], 1)
        self.assertTrue(five_lines["budget_exhausted"])
        self.assertFalse(any(block["relation"] == "import_binding" for block in five_lines["blocks"]))

    def test_method_context_includes_owner_class_header_without_unrelated_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text(
                "import click\n"
                "from extra import unrelated\n"
                "\n"
                "class PathChild(\n"
                "    click.Path,\n"
                "):\n"
                "    def convert(self, value):\n"
                "        return super().convert(value)\n"
                "    def other(self):\n"
                "        return unrelated()\n",
                encoding="utf-8",
            )
            index = build_index(root)
            full = build_context(index, "sample.py::PathChild.convert", max_lines=6)
            tight = build_context(index, "sample.py::PathChild.convert", max_lines=4)

        self.assertEqual(
            [(block["symbol"], block["relation"]) for block in full["blocks"]],
            [
                ("sample.py::PathChild.convert", "target"),
                ("sample.py::PathChild", "owner_class"),
                ("sample.py::<module import click>", "import_binding"),
            ],
        )
        self.assertEqual(
            [line["text"] for line in full["blocks"][1]["lines"]],
            ["class PathChild(", "    click.Path,", "):"],
        )
        self.assertEqual(sum(len(block["lines"]) for block in full["blocks"]), 6)
        self.assertFalse(full["budget_exhausted"])
        self.assertEqual(tight["blocks"][1]["relation"], "owner_class")
        self.assertTrue(tight["blocks"][1]["truncated"])
        self.assertTrue(tight["budget_exhausted"])
        self.assertEqual(tight["omitted_imports"], 1)

    def test_method_owner_header_does_not_expand_full_base_class(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text(
                "class Parent:\n"
                "    def helper(self):\n"
                "        return 1\n"
                "\n"
                "class Child(Parent):\n"
                "    def run(self):\n"
                "        return 2\n",
                encoding="utf-8",
            )
            index = build_index(root)
            context = build_context(index, "sample.py::Child.run", max_lines=5)

        self.assertEqual(
            [(block["symbol"], block["relation"]) for block in context["blocks"]],
            [
                ("sample.py::Child.run", "target"),
                ("sample.py::Child", "owner_class"),
            ],
        )
        self.assertEqual(sum(len(block["lines"]) for block in context["blocks"]), 3)
        self.assertFalse(context["budget_exhausted"])

    def test_method_owner_header_excludes_first_method_decorator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text(
                "class Child:\n"
                "    @staticmethod\n"
                "    def other():\n"
                "        return 1\n"
                "    def run(self):\n"
                "        return 2\n",
                encoding="utf-8",
            )
            index = build_index(root)
            context = build_context(index, "sample.py::Child.run", max_lines=5)

        owner = next(block for block in context["blocks"] if block["relation"] == "owner_class")
        self.assertEqual([line["text"] for line in owner["lines"]], ["class Child:"])

    def test_method_owner_header_excludes_comments_before_first_method(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text(
                "class Child:\n"
                "    # This describes the first method, not the class header.\n"
                "\n"
                "    def run(self):\n"
                "        return 2\n",
                encoding="utf-8",
            )
            index = build_index(root)
            context = build_context(index, "sample.py::Child.run", max_lines=5)

        owner = next(block for block in context["blocks"] if block["relation"] == "owner_class")
        self.assertEqual([line["text"] for line in owner["lines"]], ["class Child:"])

    def test_explicit_symbol_adds_subclass_source_with_shared_line_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text(
                "class Base:\n"
                "    def render(self):\n"
                "        return list(self._list)\n"
                "\n"
                "class Child(Base):\n"
                "    def __init__(self, values):\n"
                "        self._list = []\n"
                "        self.values = values\n"
                "    def __iter__(self):\n"
                "        return iter(self.values)\n",
                encoding="utf-8",
            )
            index = build_index(root)
            ordinary = build_context(index, "sample.py::Base.render", max_lines=16)
            selected = build_context(
                index, "sample.py::Base.render", max_lines=16,
                include_symbols=("sample.py::Child",),
            )
            tight = build_context(
                index, "sample.py::Base.render", max_lines=5,
                include_symbols=("sample.py::Child",),
            )

        self.assertFalse(any(block["symbol"] == "sample.py::Child" for block in ordinary["blocks"]))
        self.assertEqual(
            [(block["symbol"], block["relation"]) for block in selected["blocks"]],
            [
                ("sample.py::Base.render", "target"),
                ("sample.py::Base", "owner_class"),
                ("sample.py::Child", "user_selected"),
            ],
        )
        self.assertIn(
            "        return iter(self.values)",
            [line["text"] for line in selected["blocks"][2]["lines"]],
        )
        self.assertEqual(sum(len(block["lines"]) for block in tight["blocks"]), 5)
        self.assertTrue(tight["blocks"][2]["truncated"])
        self.assertTrue(tight["budget_exhausted"])

    def test_explicit_symbol_must_resolve_in_index(self):
        with tempfile.TemporaryDirectory() as directory:
            index = self.make_index(Path(directory))
            with self.assertRaisesRegex(ValueError, "Unknown symbol"):
                build_context(
                    index, "service.py::process", include_symbols=("outside.py::Missing",)
                )

    def test_explicit_owner_class_expands_abbreviated_header(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text(
                "class Base:\n"
                "    def render(self):\n"
                "        return self._list\n"
                "    def populate(self):\n"
                "        self._list = [1]\n",
                encoding="utf-8",
            )
            index = build_index(root)
            context = build_context(
                index, "sample.py::Base.render", max_lines=10,
                include_symbols=("sample.py::Base",),
            )

        self.assertEqual(
            [block["symbol"] for block in context["blocks"]],
            ["sample.py::Base.render", "sample.py::Base"],
        )
        self.assertEqual(context["blocks"][1]["relation"], "user_selected")
        self.assertIn(
            "    def populate(self):",
            [line["text"] for line in context["blocks"][1]["lines"]],
        )

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
            (index.root / "service.py").write_text(
                "from helpers import save\n\ndef process(value):\n    save(value)\n    return save(value)\n",
                encoding="utf-8",
            )
            duplicate_index = build_index(index.root)
            duplicate = build_impact(duplicate_index, "helpers.py::save", depth=2)

        self.assertEqual(
            [(item["symbol"], item["distance"]) for item in result["affected_symbols"]],
            [
                ("service.py::process", 1),
                ("api.py::route", 2),
                ("tests/test_service.py::test_process", 2),
            ],
        )
        self.assertEqual(result["module_importers"], ["service.py"])
        affected = {item["symbol"]: item for item in result["affected_symbols"]}
        self.assertEqual(
            [(edge["caller"], edge["callee"], edge["file"], edge["line"])
             for edge in affected["service.py::process"]["call_path_evidence"]],
            [("service.py::process", "helpers.py::save", "service.py", 4)],
        )
        self.assertEqual(
            [(edge["caller"], edge["callee"], edge["file"], edge["line"])
             for edge in affected["api.py::route"]["call_path_evidence"]],
            [("service.py::process", "helpers.py::save", "service.py", 4),
             ("api.py::route", "service.py::process", "api.py", 4)],
        )
        self.assertEqual(
            sum(edge.caller == "service.py::process" and edge.callee == "helpers.py::save"
                for edge in duplicate_index.call_edges),
            2,
        )
        duplicate_affected = {item["symbol"]: item for item in duplicate["affected_symbols"]}
        self.assertEqual(duplicate_affected["service.py::process"]["call_path_evidence"][0]["line"], 4)

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

class JSContextTests(unittest.TestCase):
    def test_selected_symbols_precede_multiline_import_and_share_budget(self):
        from tests.test_js_ts import HAS_EXTRA
        if not HAS_EXTRA:
            self.skipTest('requires optional js extra')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'app.ts').write_text("import {\n helper,\n} from './helper.js';\nexport function run() {\n return helper();\n}\nexport function extra() { return 1; }\n")
            (root / 'helper.ts').write_text('export function helper() { return 1; }\n')
            index = build_index(root, languages=('typescript',))
            full = build_context(index, 'app.ts::run', include_symbols=('app.ts::extra',))
            self.assertEqual([b['relation'] for b in full['blocks']], ['target', 'user_selected', 'callee', 'import_binding'])
            self.assertEqual([line['line'] for line in full['blocks'][-1]['lines']], [1, 2, 3])
            small = build_context(index, 'app.ts::run', 5, include_symbols=('app.ts::extra',))
            self.assertEqual(sum(len(b['lines']) for b in small['blocks']), 5)
            self.assertEqual([b['relation'] for b in small['blocks']], ['target', 'user_selected', 'callee'])
            self.assertFalse(small['blocks'][-1]['truncated'])
            self.assertTrue(small['budget_exhausted'])
            self.assertIn('calls', small['analysis']['capabilities']['typescript'])

    def test_method_owner_adds_header_instead_of_consuming_entire_class(self):
        from tests.test_js_ts import HAS_EXTRA, FIXTURES
        if not HAS_EXTRA:
            self.skipTest('requires optional js extra')
        index = build_index(FIXTURES, languages=('javascript',))
        data = build_context(index, 'core.js::Box.get', 5)
        self.assertEqual([(b['relation'], b['start_line'], b['end_line']) for b in data['blocks']],
                         [('target', 6, 6), ('owner_class', 5, 5)])
