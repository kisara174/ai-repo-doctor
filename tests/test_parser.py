import tempfile
import unittest
from pathlib import Path

from repo_doctor.model import OverloadSignature
from repo_doctor.parser import parse_python_file


class ParserTests(unittest.TestCase):
    def test_records_decorators_and_overload_aliases(self):
        source = """import typing as t
from typing_extensions import overload as ov
if TYPE_CHECKING:
    from click import group as conditional_group

@t.overload
def fetch(key: int) -> int: ...

@ov
def fetch(key: str) -> str: ...

@custom
def fetch(key):
    return key
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "api.py").write_text(source, encoding="utf-8")

            parsed = parse_python_file(root, "api.py")

        self.assertIsNone(parsed.error)
        fetch_symbols = [symbol for symbol in parsed.symbols if symbol.name == "fetch"]
        self.assertEqual([symbol.is_overload for symbol in fetch_symbols], [True, True, False])
        self.assertEqual(
            [symbol.decorators[0].line for symbol in fetch_symbols],
            [6, 9, 12],
        )
        self.assertEqual(
            [symbol.decorators[0].expression for symbol in fetch_symbols],
            ["t.overload", "ov", "custom"],
        )
        self.assertEqual(
            [symbol.decorators[0].recognized for symbol in fetch_symbols],
            ["typing.overload", "typing.overload", None],
        )
        self.assertEqual(
            [symbol.overload_signature for symbol in fetch_symbols],
            [
                OverloadSignature(6, 7, "def fetch(key: int) -> int"),
                OverloadSignature(9, 10, "def fetch(key: str) -> str"),
                None,
            ],
        )
        self.assertTrue(parsed.imports[0].is_unconditional_module_level)
        self.assertTrue(parsed.imports[1].is_unconditional_module_level)
        self.assertFalse(parsed.imports[2].is_unconditional_module_level)

    def test_conditional_overload_import_is_not_recognized(self):
        source = """if TYPE_CHECKING:
    from typing import overload as ov

@ov
def fetch(key): ...
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "api.py").write_text(source, encoding="utf-8")

            parsed = parse_python_file(root, "api.py")

        self.assertIsNone(parsed.error)
        self.assertFalse(parsed.imports[0].is_unconditional_module_level)
        self.assertFalse(parsed.symbols[0].is_overload)
        self.assertIsNone(parsed.symbols[0].decorators[0].recognized)

    def test_shadowed_overload_alias_is_not_recognized(self):
        source = """from typing import overload as ov
ov = custom

@ov
def fetch(key): ...
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "api.py").write_text(source, encoding="utf-8")

            parsed = parse_python_file(root, "api.py")

        self.assertIsNone(parsed.error)
        self.assertFalse(parsed.symbols[0].is_overload)
        self.assertIsNone(parsed.symbols[0].decorators[0].recognized)

    def test_extracts_nested_symbols_imports_and_calls_with_source_lines(self):
        source = """from .helpers import save as persist
import pkg.util as util

class Service:
    @classmethod
    async def create(cls, item):
        persist(item)
        util.log(item)
        def inner():
            return cls.check(item)
        return inner()

    def check(self, item):
        return item
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "service.py").write_text(source, encoding="utf-8")

            parsed = parse_python_file(root, "pkg/service.py")

        self.assertIsNone(parsed.error)
        self.assertEqual(parsed.file.path, "pkg/service.py")
        self.assertEqual(parsed.file.lines, 14)
        self.assertEqual(
            [(symbol.id, symbol.kind, symbol.start_line, symbol.end_line) for symbol in parsed.symbols],
            [
                ("pkg/service.py::Service", "class", 4, 14),
                ("pkg/service.py::Service.create", "method", 5, 11),
                ("pkg/service.py::Service.create.inner", "function", 9, 10),
                ("pkg/service.py::Service.check", "method", 13, 14),
            ],
        )
        self.assertEqual(
            [(item.module, item.level, item.name, item.alias, item.line) for item in parsed.imports],
            [("helpers", 1, "save", "persist", 1), ("pkg.util", 0, None, "util", 2)],
        )
        self.assertEqual(
            [(call.caller, call.expression, call.line) for call in parsed.calls],
            [
                ("pkg/service.py::Service.create", "persist", 7),
                ("pkg/service.py::Service.create", "util.log", 8),
                ("pkg/service.py::Service.create.inner", "cls.check", 10),
                ("pkg/service.py::Service.create", "inner", 11),
            ],
        )

    def test_syntax_error_is_recorded_without_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")

            parsed = parse_python_file(root, "broken.py")

        self.assertEqual(parsed.error.file, "broken.py")
        self.assertEqual(parsed.error.line, 1)
        self.assertEqual(parsed.symbols, [])

    def test_python_encoding_cookie_is_honored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "encoded.py").write_bytes(b"# coding: latin-1\nname = '\xe9'\n")

            parsed = parse_python_file(root, "encoded.py")

        self.assertIsNone(parsed.error)
        self.assertEqual(parsed.file.lines, 2)

    def test_lambda_body_call_is_not_attributed_to_enclosing_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "def save():\n    pass\n\ndef make():\n    return lambda: save()\n",
                encoding="utf-8",
            )

            parsed = parse_python_file(root, "app.py")

        self.assertEqual(parsed.calls, [])

    def test_parser_rejects_source_replaced_by_outside_symlink(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            (Path(outside) / "linked.py").write_text("def secret():\n    pass\n", encoding="utf-8")
            (root / "linked.py").symlink_to(Path(outside) / "linked.py")

            parsed = parse_python_file(root, "linked.py")

        self.assertIsNotNone(parsed.error)
        self.assertEqual(parsed.symbols, [])

    def test_generator_body_call_is_not_attributed_to_enclosing_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                "def save(value):\n    return value\n\ndef make(items):\n    return (save(item) for item in items)\n",
                encoding="utf-8",
            )

            parsed = parse_python_file(root, "app.py")

        self.assertEqual(parsed.calls, [])
