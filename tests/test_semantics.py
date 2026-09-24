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

    def test_reassigned_self_receiver_does_not_register_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.command()\n"
                "def callback():\n"
                "    pass\n"
                "class App(click.Group):\n"
                "    def install(self):\n"
                "        self = object()\n"
                "        self.add_command(callback)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(
            any(edge.kind == "command_registration" for edge in index.semantic_edges)
        )

    def test_explicit_registration_accepts_click_module_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click as c\n"
                "@c.group()\n"
                "def cli():\n"
                "    pass\n"
                "@c.command()\n"
                "def leaf():\n"
                "    pass\n"
                "cli.add_command(leaf)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertIn(
            ("app.py::cli", "app.py::leaf", "app.py", 8),
            [
                (edge.source_symbol, edge.target_symbol, edge.evidence_file, edge.line)
                for edge in index.semantic_edges
                if edge.kind == "command_registration"
            ],
        )

    def test_explicit_registration_rejects_rebound_add_command_attribute(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@click.command()\n"
                "def leaf():\n"
                "    pass\n"
                "def custom_add_command(command):\n"
                "    pass\n"
                "cli.add_command = custom_add_command\n"
                "cli.add_command(leaf)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(
            any(
                edge.kind == "command_registration" and edge.line == 11
                for edge in index.semantic_edges
            )
        )

    def test_explicit_registration_rejects_same_line_module_rebind(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@click.command()\n"
                "def leaf():\n"
                "    pass\n"
                "def custom_add_command(command):\n"
                "    pass\n"
                "cli.add_command = custom_add_command; cli.add_command(leaf)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(
            any(
                edge.kind == "command_registration" and edge.line == 10
                for edge in index.semantic_edges
            )
        )

    def test_explicit_registration_before_later_rebind_remains_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@click.command()\n"
                "def leaf():\n"
                "    pass\n"
                "def custom_add_command(command):\n"
                "    pass\n"
                "cli.add_command(leaf); cli.add_command = custom_add_command\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertIn(
            ("app.py::cli", "app.py::leaf", 10),
            [
                (edge.source_symbol, edge.target_symbol, edge.line)
                for edge in index.semantic_edges
                if edge.kind == "command_registration"
            ],
        )

    def test_module_registration_rejects_prior_helper_rebinding_global_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@click.command()\n"
                "def leaf():\n"
                "    pass\n"
                "def custom_add_command(command):\n"
                "    pass\n"
                "def patch_group():\n"
                "    cli.add_command = custom_add_command\n"
                "patch_group()\n"
                "cli.add_command(leaf)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(
            any(
                edge.kind == "command_registration" and edge.line == 13
                for edge in index.semantic_edges
            )
        )

    def test_explicit_registration_rejects_instance_method_rebind(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.command()\n"
                "def leaf():\n"
                "    pass\n"
                "def custom_add_command(command):\n"
                "    pass\n"
                "class App(click.Group):\n"
                "    def install(self):\n"
                "        self.add_command = custom_add_command\n"
                "        self.add_command(leaf)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(
            any(
                edge.kind == "command_registration" and edge.line == 10
                for edge in index.semantic_edges
            )
        )

    def test_explicit_registration_rejects_same_line_instance_method_rebind(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.command()\n"
                "def leaf():\n"
                "    pass\n"
                "def custom_add_command(command):\n"
                "    pass\n"
                "class App(click.Group):\n"
                "    def install(self):\n"
                "        self.add_command = custom_add_command; self.add_command(leaf)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(
            any(
                edge.kind == "command_registration" and edge.line == 9
                for edge in index.semantic_edges
            )
        )

    def test_explicit_registration_accepts_imported_group_alias_and_local_base_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "from click import Group as ClickGroup\n"
                "import click\n"
                "@click.command()\n"
                "def leaf():\n"
                "    pass\n"
                "class RootGroup(ClickGroup):\n"
                "    pass\n"
                "class IntermediateGroup(RootGroup):\n"
                "    pass\n"
                "class AppGroup(IntermediateGroup):\n"
                "    def register(self):\n"
                "        def helper(self):\n"
                "            self = object()\n"
                "        self.add_command(leaf)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertIn(
            ("app.py::AppGroup", "app.py::leaf", "app.py", 14),
            [
                (edge.source_symbol, edge.target_symbol, edge.evidence_file, edge.line)
                for edge in index.semantic_edges
                if edge.kind == "command_registration"
            ],
        )

    def test_explicit_registration_does_not_assume_overridden_add_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.command()\n"
                "def leaf():\n"
                "    pass\n"
                "class BaseGroup(click.Group):\n"
                "    def add_command(self, command, name=None):\n"
                "        self.last_command = command\n"
                "class AppGroup(BaseGroup):\n"
                "    def install(self):\n"
                "        self.add_command(leaf)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        registration_edges = [
            (edge.kind, edge.source_symbol, edge.target_symbol)
            for edge in index.semantic_edges
            if edge.kind == "command_registration"
        ]
        self.assertEqual(registration_edges, [])

    def test_explicit_registration_does_not_assume_class_attribute_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.command()\n"
                "def leaf():\n"
                "    pass\n"
                "def ignore_command(self, command, name=None):\n"
                "    self.last_command = command\n"
                "class AppGroup(click.Group):\n"
                "    add_command = ignore_command\n"
                "    def install(self):\n"
                "        self.add_command(leaf)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        registration_edges = [
            (edge.kind, edge.source_symbol, edge.target_symbol)
            for edge in index.semantic_edges
            if edge.kind == "command_registration"
        ]
        self.assertEqual(registration_edges, [])

    def test_explicit_registration_accepts_decorator_registered_subgroup_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "import click\n"
                "@click.group()\n"
                "def cli():\n"
                "    pass\n"
                "@cli.group()\n"
                "def nested():\n"
                "    pass\n"
                "cli.add_command(nested)\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertIn(
            ("app.py::cli", "app.py::nested", "app.py", 8),
            [
                (edge.source_symbol, edge.target_symbol, edge.evidence_file, edge.line)
                for edge in index.semantic_edges
                if edge.kind == "command_registration"
            ],
        )

    def test_unproven_explicit_registration_near_misses_do_not_create_edges(self):
        prefix = (
            "import click\n"
            "@click.group()\n"
            "def cli():\n"
            "    pass\n"
            "@click.command()\n"
            "def leaf():\n"
            "    pass\n"
        )
        fixtures = {
            "non-Click instance": prefix
            + "class App:\n"
            + "    def install(self):\n"
            + "        self.add_command(leaf)\n",
            "receiver rebound": prefix
            + "cli = object()\n"
            + "cli.add_command(leaf)\n",
            "callback rebound": prefix
            + "leaf = object()\n"
            + "cli.add_command(leaf)\n",
            "unknown receiver": prefix + "other.add_command(leaf)\n",
            "attribute receiver": prefix + "app.cli.add_command(leaf)\n",
            "dynamic callback arguments": prefix
            + "class App(click.Group):\n"
            + "    def install(self):\n"
            + "        self.add_command(*commands)\n"
            + "        self.add_command(cmd=leaf)\n",
            "method-local callback shadow": prefix
            + "class App(click.Group):\n"
            + "    def install(self, leaf):\n"
            + "        self.add_command(leaf)\n",
        }

        for case, source in fixtures.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
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
