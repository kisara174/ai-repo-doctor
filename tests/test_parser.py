import tempfile
import unittest
from pathlib import Path

from repo_doctor.parser import parse_python_file


class ParserTests(unittest.TestCase):
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
