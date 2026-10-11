"""Behavioral regressions for conservative Python call binding."""
import tempfile
import unittest
from pathlib import Path
from repo_doctor.index import build_index


class PythonBindingSafetyTests(unittest.TestCase):
    def make_index(self, source):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'app.py').write_text(source, encoding='utf-8')
        return build_index(root)

    def edges(self, index):
        return {(e.caller, e.callee) for e in index.call_edges}

    def test_comprehension_bindings_do_not_shadow_outer_call(self):
        for expression in ('[helper for helper in (1, 2)]',
                           '{helper for helper in (1, 2)}',
                           '{helper: helper for helper in (1, 2)}',
                           '(helper for helper in (1, 2))'):
            with self.subTest(expression=expression):
                index = self.make_index('def helper():\n    return 1\n'
                    'def caller():\n    values = ' + expression + '\n    return helper()\n')
                self.assertIn(('app.py::caller', 'app.py::helper'), self.edges(index))

    def test_nested_body_binding_does_not_shadow_outer_call(self):
        index = self.make_index('def helper():\n    return 1\n'
            'def caller():\n    def nested():\n        helper = 1\n'
            '    return helper()\n')
        self.assertIn(('app.py::caller', 'app.py::helper'), self.edges(index))

    def test_real_bindings_remain_shadowing(self):
        for binding in ('helper = 1', 'import math as helper',
                        'try:\n        pass\n    except ValueError as helper:\n        pass',
                        'values = [(helper := item) for item in (1, 2)]'):
            with self.subTest(binding=binding):
                index = self.make_index('def helper():\n    return 1\n'
                    'def caller():\n    ' + binding + '\n    return helper()\n')
                self.assertNotIn(('app.py::caller', 'app.py::helper'), self.edges(index))

    def test_definition_creation_binding_is_in_outer_scope(self):
        index = self.make_index('def helper():\n    return 1\n'
            'def caller():\n    def nested(value=(helper := 1)):\n        pass\n'
            '    return helper()\n')
        self.assertNotIn(('app.py::caller', 'app.py::helper'), self.edges(index))
