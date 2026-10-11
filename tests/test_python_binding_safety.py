"""Behavioral regressions for conservative Python call binding."""
import tempfile
import unittest
from pathlib import Path
from repo_doctor.index import build_index
from repo_doctor.context import build_context, build_impact
from repo_doctor.repo_map import build_map


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

    def test_comprehension_calls_do_not_resolve_shadowed_global(self):
        for expression in ('[helper() for helper in callbacks]',
                           '{helper() for helper in callbacks}',
                           '{helper(): 1 for helper in callbacks}',
                           '(helper() for helper in callbacks)',
                           '[item for helper in callbacks if helper()]',
                           '[[helper() for item in helper()] for helper in callbacks]'):
            with self.subTest(expression=expression):
                index = self.make_index('def helper():\n    return 1\n'
                    'def caller(callbacks):\n    return ' + expression + '\n')
                self.assertNotIn(('app.py::caller', 'app.py::helper'), self.edges(index))
                self.assertFalse(build_context(index, 'app.py::caller')['call_evidence'])
                self.assertFalse(build_impact(index, 'app.py::helper')['affected_symbols'])
                self.assertFalse(any(e['kind'] == 'call' for e in build_map(index)['edges']))

    def test_comprehension_first_iterable_uses_outer_scope(self):
        index = self.make_index('def helper():\n    return []\n'
            'def caller():\n    return [\n        helper()\n'
            '        for helper in helper()\n    ]\n')
        evidence = build_context(index, 'app.py::caller')['call_evidence']
        self.assertEqual([(e['callee'], e['line']) for e in evidence], [('app.py::helper', 6)])

    def test_comprehension_unshadowed_calls_remain_resolved(self):
        index = self.make_index('def helper():\n    return 1\n'
            'def caller(items):\n    return [helper() for item in items]\n')
        self.assertIn(('app.py::caller', 'app.py::helper'), self.edges(index))

    def test_comprehension_receiver_is_not_original_self(self):
        index = self.make_index('class Worker:\n    def work(self):\n        return 1\n'
            '    def caller(self, others):\n        return [self.work() for self in others]\n')
        self.assertNotIn(('app.py::Worker.caller', 'app.py::Worker.work'), self.edges(index))

    def test_comprehension_bindings_block_import_reexport_fallback(self):
        for statement, expression in (
            ('from library import helper', '[helper() for helper in items]'),
            ('import library', '[library.helper() for library in items]'),
        ):
            with self.subTest(statement=statement):
                directory = tempfile.TemporaryDirectory()
                self.addCleanup(directory.cleanup)
                root = Path(directory.name)
                (root / 'library.py').write_text('def helper():\n    return 1\n')
                (root / 'app.py').write_text(statement + '\ndef caller(items):\n    return ' + expression + '\n')
                index = build_index(root)
                self.assertNotIn(('app.py::caller', 'library.py::helper'), self.edges(index))
                self.assertFalse(build_context(index, 'app.py::caller')['call_evidence'])
                self.assertFalse(build_impact(index, 'library.py::helper')['affected_symbols'])

    def test_enclosing_binding_blocks_import_reexport_fallback(self):
        for statement, binding, expression in (
            ('from library import helper', 'helper = None', 'helper()'),
            ('import library', 'library = None', 'library.helper()'),
        ):
            with self.subTest(statement=statement):
                directory = tempfile.TemporaryDirectory()
                self.addCleanup(directory.cleanup)
                root = Path(directory.name)
                (root / 'library.py').write_text('def helper():\n    return 1\n')
                (root / 'app.py').write_text(statement + '\ndef outer():\n    ' + binding
                    + '\n    def inner():\n        return ' + expression + '\n    return inner()\n')
                index = build_index(root)
                self.assertNotIn(('app.py::outer.inner', 'library.py::helper'), self.edges(index))

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

    def test_enclosing_binding_blocks_global_fallback(self):
        for outer_binding in ('def helper():\n        return 2', 'helper = 2'):
            with self.subTest(binding=outer_binding):
                index = self.make_index('def helper():\n    return 1\n'
                    'def outer():\n    ' + outer_binding + '\n'
                    '    def inner():\n        return helper()\n    return inner()\n')
                self.assertNotIn(('app.py::outer.inner', 'app.py::helper'), self.edges(index))
                context = build_context(index, 'app.py::outer.inner')
                self.assertFalse(any(e['callee'] == 'app.py::helper' for e in context['call_evidence']))
                impact = build_impact(index, 'app.py::helper')
                self.assertNotIn('app.py::outer.inner', {row['symbol'] for row in impact['affected_symbols']})
                self.assertFalse(any(e['kind'] == 'call'
                    and e['source'] == 'symbol:app.py::outer.inner'
                    and e['target'] == 'symbol:app.py::helper' for e in build_map(index)['edges']))

    def test_enclosing_scope_without_binding_preserves_module_call(self):
        index = self.make_index('def helper():\n    return 1\n'
            'def outer():\n    def inner():\n        return helper()\n    return inner()\n')
        self.assertIn(('app.py::outer.inner', 'app.py::helper'), self.edges(index))

    def test_class_attributes_are_not_method_lexical_bindings(self):
        index = self.make_index('def helper():\n    return 1\n'
            'class Worker:\n    helper = 2\n    def caller(self):\n        return helper()\n')
        self.assertIn(('app.py::Worker.caller', 'app.py::helper'), self.edges(index))

    def test_rebound_nested_function_is_unresolved(self):
        for change in ('helper = replacement', 'del helper',
                       'import math as helper', 'helper += replacement'):
            with self.subTest(change=change):
                index = self.make_index('def replacement():\n    return 2\n'
                    'def caller():\n    def helper():\n        return 1\n'
                    '    ' + change + '\n    return helper()\n')
                self.assertNotIn(('app.py::caller', 'app.py::caller.helper'), self.edges(index))

    def test_conditional_nested_definition_is_not_a_stable_target(self):
        index = self.make_index('def caller(flag):\n    if flag:\n'
            '        def helper():\n            return 1\n    return helper()\n')
        self.assertNotIn(('app.py::caller', 'app.py::caller.helper'), self.edges(index))

    def test_stable_nested_definition_remains_resolved(self):
        index = self.make_index('def caller():\n    def helper():\n        return 1\n    return helper()\n')
        self.assertIn(('app.py::caller', 'app.py::caller.helper'), self.edges(index))

    def test_nested_nonlocal_write_blocks_stable_callable(self):
        index = self.make_index('def caller():\n    def helper():\n        return 1\n'
            '    def mutate():\n        nonlocal helper\n        helper = None\n'
            '    mutate()\n    return helper()\n')
        self.assertNotIn(('app.py::caller', 'app.py::caller.helper'), self.edges(index))

    def test_rebound_self_does_not_resolve_original_method(self):
        for change in ('self = Other()', 'del self', 'self += 1', 'self, other = (Other(), 1)',
                       'def mutate():\n            nonlocal self\n            self = Other()\n        mutate()'):
            with self.subTest(change=change):
                index = self.make_index('class Other:\n    def work(self):\n        return 1\n'
                    'class Worker:\n    def work(self):\n        return 2\n'
                    '    def caller(self):\n        ' + change + '\n        return self.work()\n')
                self.assertNotIn(('app.py::Worker.caller', 'app.py::Worker.work'), self.edges(index))

    def test_normal_instance_method_self_call_remains_resolved(self):
        index = self.make_index('class Worker:\n    def work(self):\n        return 2\n'
            '    def caller(self):\n        return self.work()\n')
        self.assertIn(('app.py::Worker.caller', 'app.py::Worker.work'), self.edges(index))

    def test_self_named_static_or_class_parameter_is_not_instance_receiver(self):
        for decorator in ('staticmethod', 'classmethod'):
            with self.subTest(decorator=decorator):
                index = self.make_index('class Worker:\n    def work(self):\n        return 2\n'
                    '    @' + decorator + '\n    def caller(self):\n        return self.work()\n')
                self.assertNotIn(('app.py::Worker.caller', 'app.py::Worker.work'), self.edges(index))
