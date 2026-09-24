import tempfile
import unittest
from pathlib import Path

from repo_doctor.index import build_index


class GraphTests(unittest.TestCase):
    def test_resolves_method_call_on_locally_constructed_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n"
                "    def send(self):\n        return 1\n"
                "\ndef run():\n"
                "    client = Client()\n"
                "    return client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertIn(
            ("app.py::run", "app.py::Client.send"),
            [(edge.caller, edge.callee) for edge in index.call_edges],
        )

    def test_resolves_same_line_call_after_local_construction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n    def send(self):\n        pass\n\n"
                "def run(): client = Client(); client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertIn("app.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_conditional_constructor_binding_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n    def send(self):\n        pass\n\n"
                "def run(flag):\n"
                "    if flag:\n        client = Client()\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee == "app.py::Client.send" for edge in index.call_edges))

    def test_resolves_instance_created_by_imported_module_context_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
            (root / "pkg" / "sessions.py").write_text(
                "class Session:\n"
                "    def __enter__(self):\n        return self\n"
                "    def __exit__(self, exc_type, exc, tb):\n        return False\n"
                "    def request(self):\n        return 1\n",
                encoding="utf-8",
            )
            (root / "pkg" / "api.py").write_text(
                "from . import sessions\n\n"
                "def request():\n"
                "    with sessions.Session() as session:\n"
                "        return session.request()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertIn(
            ("pkg/api.py::request", "pkg/sessions.py::Session.request"),
            [(edge.caller, edge.callee) for edge in index.call_edges],
        )

    def test_ambiguous_local_instance_types_remain_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class First:\n    def send(self):\n        pass\n\n"
                "class Second:\n    def send(self):\n        pass\n\n"
                "def run(flag):\n"
                "    if flag:\n        client = First()\n"
                "    else:\n        client = Second()\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee.endswith(("First.send", "Second.send")) for edge in index.call_edges))

    def test_reassigned_local_instance_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n    def send(self):\n        pass\n\n"
                "def run():\n"
                "    client = Client()\n"
                "    client = None\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee == "app.py::Client.send" for edge in index.call_edges))

    def test_reassigned_to_same_constructor_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n    def send(self):\n        pass\n\n"
                "def run():\n"
                "    client = Client()\n"
                "    client = Client()\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee == "app.py::Client.send" for edge in index.call_edges))

    def test_call_before_local_construction_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n    def send(self):\n        pass\n\n"
                "def run():\n"
                "    client.send()\n"
                "    client = Client()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee == "app.py::Client.send" for edge in index.call_edges))

    def test_module_rebinding_of_class_name_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n    def send(self):\n        pass\n\n"
                "Client = object\n\n"
                "def run():\n"
                "    client = Client()\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee == "app.py::Client.send" for edge in index.call_edges))

    def test_local_class_and_imported_class_name_collision_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "other.py").write_text(
                "class Client:\n    def send(self):\n        return 'other'\n",
                encoding="utf-8",
            )
            (root / "app.py").write_text(
                "from other import Client\n\n"
                "class Client:\n    def send(self):\n        return 'local'\n\n"
                "def run():\n"
                "    client = Client()\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee.endswith(".send") for edge in index.call_edges))

    def test_local_class_shadows_imported_module_alias_in_constructor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "other.py").write_text(
                "class Client:\n    def send(self):\n        return 'other'\n",
                encoding="utf-8",
            )
            (root / "app.py").write_text(
                "import other as clients\n\n"
                "class clients:\n"
                "    class Client:\n"
                "        def send(self):\n            return 'local'\n\n"
                "def run():\n"
                "    client = clients.Client()\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertNotIn("other.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_local_function_shadows_imported_class_in_constructor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "other.py").write_text(
                "class Client:\n    def send(self):\n        return 'other'\n",
                encoding="utf-8",
            )
            (root / "app.py").write_text(
                "from other import Client\n\n"
                "def Client():\n    return None\n\n"
                "def run():\n"
                "    client = Client()\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertNotIn("other.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_match_capture_rebinding_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n    def send(self):\n        pass\n\n"
                "def run(value):\n"
                "    client = Client()\n"
                "    match value:\n"
                "        case {'client': client}:\n"
                "            client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee == "app.py::Client.send" for edge in index.call_edges))

    def test_context_manager_binding_requires_enter_to_return_self(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Inner:\n    def send(self):\n        pass\n\n"
                "class Wrapper:\n"
                "    def __enter__(self):\n        return Inner()\n"
                "    def send(self):\n        pass\n\n"
                "def run():\n"
                "    with Wrapper() as client:\n"
                "        client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee == "app.py::Wrapper.send" for edge in index.call_edges))

    def test_async_context_manager_uses_aenter_return_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Inner:\n    def send(self):\n        pass\n\n"
                "class Wrapper:\n"
                "    def __enter__(self):\n        return self\n"
                "    async def __aenter__(self):\n        return Inner()\n"
                "    async def __aexit__(self, exc_type, exc, tb):\n        return False\n"
                "    def send(self):\n        pass\n\n"
                "async def run():\n"
                "    async with Wrapper() as client:\n"
                "        client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee == "app.py::Wrapper.send" for edge in index.call_edges))

    def test_async_context_manager_resolves_when_aenter_returns_self(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n"
                "    async def __aenter__(self):\n        return self\n"
                "    async def __aexit__(self, exc_type, exc, tb):\n        return False\n"
                "    def send(self):\n        pass\n\n"
                "async def run():\n"
                "    async with Client() as client:\n"
                "        client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertIn("app.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_sync_with_rejects_async_enter_method(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n"
                "    async def __enter__(self):\n        return self\n"
                "    def __exit__(self, exc_type, exc, tb):\n        return False\n"
                "    def send(self):\n        pass\n\n"
                "def run():\n"
                "    with Client() as client:\n"
                "        client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertNotIn("app.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_async_with_rejects_sync_aenter_method(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n"
                "    def __aenter__(self):\n        return self\n"
                "    async def __aexit__(self, exc_type, exc, tb):\n        return False\n"
                "    def send(self):\n        pass\n\n"
                "async def run():\n"
                "    async with Client() as client:\n"
                "        client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertNotIn("app.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_sync_with_rejects_enter_method_with_required_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n"
                "    def __enter__(self, required):\n        return self\n"
                "    def __exit__(self, exc_type, exc, tb):\n        return False\n"
                "    def send(self):\n        pass\n\n"
                "def run():\n"
                "    with Client() as client:\n"
                "        client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertNotIn("app.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_async_with_rejects_aenter_method_with_required_keyword_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n"
                "    async def __aenter__(self, *, required):\n        return self\n"
                "    async def __aexit__(self, exc_type, exc, tb):\n        return False\n"
                "    def send(self):\n        pass\n\n"
                "async def run():\n"
                "    async with Client() as client:\n"
                "        client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertNotIn("app.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_context_manager_requires_matching_exit_method(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n"
                "    def __enter__(self):\n        return self\n"
                "    def send(self):\n        pass\n\n"
                "def run():\n"
                "    with Client() as client:\n"
                "        client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertNotIn("app.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_async_context_manager_requires_matching_aexit_method(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n"
                "    async def __aenter__(self):\n        return self\n"
                "    def send(self):\n        pass\n\n"
                "async def run():\n"
                "    async with Client() as client:\n"
                "        client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertNotIn("app.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_with_body_assignment_is_not_assumed_unconditional(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n    def send(self):\n        pass\n\n"
                "class Suppress:\n"
                "    def __enter__(self):\n        return self\n"
                "    def __exit__(self, exc_type, exc, tb):\n        return True\n\n"
                "def run():\n"
                "    with Suppress():\n"
                "        raise ValueError()\n"
                "        client = Client()\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertNotIn("app.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_nonlocal_rebinding_invalidates_outer_constructor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n    def send(self):\n        pass\n\n"
                "class Other:\n    def send(self):\n        pass\n\n"
                "def run():\n"
                "    client = Client()\n"
                "    def replace():\n"
                "        nonlocal client\n"
                "        client = Other()\n"
                "    replace()\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertNotIn("app.py::Client.send", [edge.callee for edge in index.call_edges])

    def test_shadowed_constructor_name_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "class Client:\n    def send(self):\n        pass\n\n"
                "def run(Client):\n"
                "    client = Client()\n"
                "    client.send()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertFalse(any(edge.callee == "app.py::Client.send" for edge in index.call_edges))

    def test_resolves_relative_imports_aliases_and_self_methods(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
            (root / "pkg" / "helpers.py").write_text("def save(item):\n    return item\n", encoding="utf-8")
            (root / "pkg" / "service.py").write_text(
                "from .helpers import save as persist\n"
                "import pkg.helpers as h\n\n"
                "class Service:\n"
                "    def run(self, item):\n"
                "        persist(item)\n"
                "        h.save(item)\n"
                "        self.done(item)\n"
                "        unknown(item)\n\n"
                "    def done(self, item):\n"
                "        return item\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertEqual(
            [(edge.source, edge.target, edge.line) for edge in index.import_edges],
            [("pkg/service.py", "pkg/helpers.py", 1), ("pkg/service.py", "pkg/helpers.py", 2)],
        )
        self.assertEqual(
            [(edge.caller, edge.callee, edge.line) for edge in index.call_edges],
            [
                ("pkg/service.py::Service.run", "pkg/helpers.py::save", 6),
                ("pkg/service.py::Service.run", "pkg/helpers.py::save", 7),
                ("pkg/service.py::Service.run", "pkg/service.py::Service.done", 8),
            ],
        )
        self.assertEqual(len(index.calls) - len(index.call_edges), 1)

    def test_shadowed_parameter_is_not_assumed_to_be_module_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "def save():\n    pass\n\ndef run(save):\n    save()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertEqual(index.call_edges, [])

    def test_src_layout_resolves_project_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src" / "pkg").mkdir(parents=True)
            (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
            (root / "src" / "pkg" / "helper.py").write_text("def foo():\n    pass\n", encoding="utf-8")
            (root / "src" / "pkg" / "run.py").write_text(
                "from pkg.helper import foo\n\ndef execute():\n    foo()\n", encoding="utf-8"
            )

            index = build_index(root)

        self.assertEqual(index.import_edges[0].target, "src/pkg/helper.py")
        self.assertEqual(index.call_edges[0].callee, "src/pkg/helper.py::foo")

    def test_plain_dotted_import_binds_package_not_submodule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
            (root / "pkg" / "helpers.py").write_text("def save():\n    pass\n", encoding="utf-8")
            (root / "app.py").write_text(
                "import pkg.helpers\n\ndef run():\n    pkg.save()\n", encoding="utf-8"
            )

            index = build_index(root)

        self.assertEqual(index.call_edges, [])

    def test_import_cycle_is_reported_deterministically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.py").write_text("import b\n", encoding="utf-8")
            (root / "b.py").write_text("import a\n", encoding="utf-8")

            index = build_index(root)

        self.assertEqual(index.import_cycles, [["a.py", "b.py"]])

    def test_long_acyclic_import_chain_does_not_hit_recursion_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number in range(1100):
                next_import = f"import m{number + 1}\n" if number < 1099 else ""
                (root / f"m{number}.py").write_text(next_import, encoding="utf-8")

            index = build_index(root)

        self.assertEqual(index.import_cycles, [])
        self.assertEqual(len(index.import_edges), 1099)

    def test_relative_import_beyond_package_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
            (root / "foo.py").write_text("def bar():\n    pass\n", encoding="utf-8")
            (root / "pkg" / "service.py").write_text(
                "from ..foo import bar\n\ndef run():\n    bar()\n", encoding="utf-8"
            )

            index = build_index(root)

        self.assertEqual(index.import_edges, [])
        self.assertEqual(index.call_edges, [])

    def test_multiple_names_from_one_module_make_one_import_edge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
            (root / "pkg" / "helpers.py").write_text(
                "def one():\n    pass\n\ndef two():\n    pass\n", encoding="utf-8"
            )
            (root / "pkg" / "service.py").write_text(
                "from .helpers import one, two\n\ndef run():\n    one()\n    two()\n", encoding="utf-8"
            )

            index = build_index(root)

        self.assertEqual(len(index.import_edges), 1)
        self.assertEqual(len(index.call_edges), 2)

    def test_external_import_shadowing_local_alias_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local.py").write_text("def save():\n    pass\n", encoding="utf-8")
            (root / "app.py").write_text(
                "from local import save\nfrom external import save\n\ndef run():\n    save()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertEqual(index.call_edges, [])

    def test_module_assignment_shadowing_import_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local.py").write_text("def save():\n    pass\n", encoding="utf-8")
            (root / "app.py").write_text(
                "from local import save\nsave = lambda: None\n\ndef run():\n    save()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertEqual(index.call_edges, [])

    def test_local_import_then_reassignment_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local.py").write_text("def save():\n    pass\n", encoding="utf-8")
            (root / "app.py").write_text(
                "def run():\n    from local import save\n    save = lambda: None\n    save()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertEqual(index.call_edges, [])

    def test_external_import_shadowing_same_file_function_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "def save():\n    pass\n\nfrom external import save\n\ndef run():\n    save()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertEqual(index.call_edges, [])

    def test_module_function_shadowing_import_alias_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local.py").write_text("def save():\n    pass\n", encoding="utf-8")
            (root / "app.py").write_text(
                "import local as h\n\ndef h():\n    pass\n\ndef run():\n    h.save()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertEqual(index.call_edges, [])

    def test_dotted_import_with_explicit_first_segment_alias_binds_submodule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("def run():\n    return 0\n", encoding="utf-8")
            (root / "pkg" / "mod.py").write_text("def run():\n    return 1\n", encoding="utf-8")
            (root / "app.py").write_text(
                "import pkg.mod as pkg\n\ndef call():\n    pkg.run()\n", encoding="utf-8"
            )

            index = build_index(root)

        self.assertEqual(index.call_edges[0].callee, "pkg/mod.py::run")

    def test_package_relative_import_does_not_create_self_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("from . import helper\n", encoding="utf-8")
            (root / "pkg" / "helper.py").write_text("pass\n", encoding="utf-8")

            index = build_index(root)

        self.assertEqual(
            [(edge.source, edge.target, edge.line) for edge in index.import_edges],
            [("pkg/__init__.py", "pkg/helper.py", 1)],
        )
        self.assertEqual(index.import_cycles, [])

    def test_duplicate_conditional_definitions_remain_ambiguous(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "if FLAG:\n"
                "    def target():\n        return 1\n"
                "else:\n"
                "    def target():\n        return 2\n"
                "\ndef caller():\n    return target()\n",
                encoding="utf-8",
            )

            index = build_index(root)

        self.assertEqual(index.ambiguous_symbols, {"app.py::target"})
        self.assertNotIn("app.py::target", index.symbols)
        self.assertEqual(index.call_edges, [])
