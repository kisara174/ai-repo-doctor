import tempfile
import unittest
from pathlib import Path

from repo_doctor.index import build_index


class ClickSemanticTests(unittest.TestCase):
    def test_click_module_alias_registers_commands_and_subgroups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click as c\n"
                "@c.group()\n"
                "def cli():\n"
                "    pass\n"
                "@cli.command()\n"
                "def leaf():\n"
                "    pass\n"
                "@cli.group()\n"
                "def nested():\n"
                "    pass\n"
                "@nested.command()\n"
                "def deep_leaf():\n"
                "    pass\n",
                encoding="utf-8",
            )

            index = build_index(root)

        registration_edges = [
            edge for edge in index.semantic_edges if edge.kind == "command_registration"
        ]
        self.assertEqual(
            [
                (edge.source_symbol, edge.target_symbol, edge.evidence_file, edge.line)
                for edge in registration_edges
            ],
            [
                ("app.py::cli", "app.py::leaf", "app.py", 5),
                ("app.py::cli", "app.py::nested", "app.py", 8),
                ("app.py::nested", "app.py::deep_leaf", "app.py", 11),
            ],
        )

    def test_direct_click_import_aliases_are_recognized_without_registration_edge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "from click import group as make_group\n"
                "from click import command as make_command\n"
                "@make_group()\n"
                "def cli():\n"
                "    pass\n"
                "@make_command()\n"
                "def standalone():\n"
                "    pass\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertEqual(index.symbols["app.py::cli"].decorators[0].recognized, "click.group")
        self.assertEqual(
            index.symbols["app.py::standalone"].decorators[0].recognized,
            "click.command",
        )
        self.assertFalse(
            any(edge.kind == "command_registration" for edge in index.semantic_edges)
        )

    def test_unrecognized_or_ambiguous_click_forms_do_not_register(self):
        fixtures = {
            "custom decorator receiver": (
                "@custom.group()\n"
                "def cli():\n"
                "    pass\n"
                "@cli.command()\n"
                "def child():\n"
                "    pass\n",
                False,
            ),
            "reassigned group name": (
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "cli = object\n"
                "@cli.command()\n"
                "def child():\n"
                "    pass\n",
                False,
            ),
            "reassigned Click module alias": (
                "import click\n"
                "click = object\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@cli.command()\n"
                "def child():\n"
                "    pass\n",
                False,
            ),
            "bare Click decorator": (
                "import click\n"
                "@click.group\n"
                "def cli():\n"
                "    pass\n"
                "@cli.command()\n"
                "def child():\n"
                "    pass\n",
                False,
            ),
            "unknown registration receiver": (
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@other.command()\n"
                "def child():\n"
                "    pass\n",
                False,
            ),
            "callback name conflicts with import": (
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@cli.command()\n"
                "def child():\n"
                "    pass\n"
                "from elsewhere import child\n",
                False,
            ),
            "duplicate callback ID": (
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@cli.command()\n"
                "def child():\n"
                "    pass\n"
                "@cli.command()\n"
                "def child():\n"
                "    pass\n",
                False,
            ),
            "conditional Click import": (
                "if True:\n"
                "    import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@cli.command()\n"
                "def child():\n"
                "    pass\n",
                False,
            ),
            "local unrelated click module": (
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@cli.command()\n"
                "def child():\n"
                "    pass\n",
                True,
            ),
        }

        for case, (source, add_local_click_module) in fixtures.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if add_local_click_module:
                    (root / "click.py").write_text("value = 1\n", encoding="utf-8")
                (root / "app.py").write_text(source, encoding="utf-8")

                index = build_index(root)

                self.assertFalse(
                    any(edge.kind == "command_registration" for edge in index.semantic_edges)
                )

    def test_unknown_decorators_keep_generic_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "@custom.decorator()\n"
                "def function():\n"
                "    pass\n",
                encoding="utf-8",
            )

            index = build_index(root)

        decorator = index.symbols["app.py::function"].decorators[0]
        self.assertEqual(decorator.expression, "custom.decorator()")
        self.assertEqual(decorator.line, 1)
        self.assertIsNone(decorator.recognized)

    def test_class_scope_binding_does_not_inherit_click_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "class Example:\n"
                "    click = object()\n"
                "    @click.group()\n"
                "    def cli():\n"
                "        pass\n",
                encoding="utf-8",
            )

            index = build_index(root)

        decorator = index.symbols["app.py::Example.cli"].decorators[0]
        self.assertIsNone(decorator.recognized)


if __name__ == "__main__":
    unittest.main()
