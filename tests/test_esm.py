"""Finite ESM file resolution never guesses ambiguous or excluded sources."""

from pathlib import Path
import tempfile
import unittest

from repo_doctor.index import build_index
from tests.test_js_ts import HAS_EXTRA


@unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
class ESMTests(unittest.TestCase):
    def test_limit_dedup_work_is_bounded_and_preserves_existing_order(self):
        from unittest.mock import patch
        from repo_doctor.esm import resolve_esm_graph
        from repo_doctor.model import AnalysisLimit

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            calls = [f'  missing{i}();' for i in range(120)]
            (root / 'app.js').write_text('export function entry() {\n' + '\n'.join(calls) + '\n}')
            index = build_index(root, languages=('javascript',))
            existing = [AnalysisLimit('earlier.js', i, 'external-or-alias', f'earlier-{i}')
                        for i in range(250)]
            wanted = [AnalysisLimit('app.js', i + 2, 'unresolved-call',
                      f'Call missing{i} is outside unique unshadowed direct function bindings')
                      for i in range(120)]
            index.analysis_limits = existing + wanted[:1]
            comparisons = 0
            original_eq = AnalysisLimit.__eq__

            def counted_eq(left, right):
                nonlocal comparisons
                comparisons += 1
                return original_eq(left, right)

            with patch.object(AnalysisLimit, '__eq__', counted_eq):
                resolve_esm_graph(index)
                resolve_esm_graph(index)
            self.assertEqual(index.analysis_limits, existing + wanted)
            self.assertEqual(index.call_edges, [])
            self.assertLess(comparisons, 600, 'dedup must not scan the growing limits list')

    def test_ts_js_substitution_unique_but_not_ambiguous_or_unselected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'core.ts').write_text('export function inc(v: number) { return v+1; }')
            (root / 'app.ts').write_text("import {inc} from './core.js';\nexport {inc as step} from './core.js';")
            index = build_index(root, languages=('typescript',))
            self.assertEqual([(e.source, e.target, e.line) for e in index.import_edges],
                             [('app.ts', 'core.ts', 1), ('app.ts', 'core.ts', 2)])
            self.assertEqual(index.esm_imports[0].resolved_file, 'core.ts')
            for name in ('core.js', 'core.d.ts', 'core.tsx'):
                (root / name).write_text('')
                self.assertEqual(build_index(root, languages=('typescript',)).import_edges, [])
                (root / name).unlink()

    def test_external_dynamic_extensionless_invalid_and_type_only_do_not_become_runtime_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'core.ts').write_text('export function inc(v: number) { return v+1; }')
            (root / 'app.ts').write_text("import type {inc} from './core.js';\nimport {inc as a} from 'pkg';\nimport {inc as b} from './core';\nexport function run() { import('./core.js'); return a(1); }")
            index = build_index(root, languages=('typescript',))
            self.assertTrue(index.esm_imports[0].type_only)
            self.assertEqual(index.call_edges, [])
            self.assertNotIn(('app.ts', 'core.ts', 3), [(e.source, e.target, e.line) for e in index.import_edges])
            self.assertTrue(any(l.reason == 'external-or-alias' for l in index.analysis_limits))
            self.assertTrue(any(l.reason == 'unresolved-call' for l in index.analysis_limits))
@unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
class DirectCallTests(unittest.TestCase):
    def test_fixture_calls_and_unique_ts_type_only_negative(self):
        import shutil
        from tests.test_js_ts import FIXTURES
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'mixed'
            shutil.copytree(FIXTURES, root)
            index = build_index(root, languages=('javascript', 'typescript'))
            pairs = {(e.caller, e.callee) for e in index.call_edges}
            self.assertIn(('core.js::twice', 'core.js::add'), pairs)
            self.assertIn(('core.js::main', 'core.js::twice'), pairs)
            self.assertNotIn(('consumer.ts::run', 'core.ts::inc'), pairs)
            self.assertFalse(any(c.startswith(('shadow.js::', 'dynamic.js::', 'type_only.ts::')) for c, _ in pairs))
            unique = Path(directory) / 'unique'
            unique.mkdir()
            for name in ('core.ts', 'consumer.ts', 'type_only.ts'):
                shutil.copyfile(FIXTURES / name, unique / name)
            index = build_index(unique, languages=('typescript',))
            self.assertIn(('consumer.ts::run', 'core.ts::inc', 3),
                          {(e.caller, e.callee, e.line) for e in index.call_edges})
            self.assertFalse(any(e.caller == 'type_only.ts::bad' for e in index.call_edges))
            from repo_doctor.context import build_impact
            impact = build_impact(index, 'core.ts::inc')
            self.assertTrue(any(a['symbol'] == 'consumer.ts::run' and
                                a['call_path_evidence'][0]['line'] == 3 for a in impact['affected_symbols']))

    def test_rewrites_locals_blocks_methods_and_callbacks_do_not_get_false_edges(self):
        cases = [
            'export function target() { return 1; }\ntarget = () => 2;\nexport function entry() { return target(); }',
            'function target() {}\nfunction entry(target) { return target(); }',
            'function target() {}\nfunction entry() { let target = () => 1; return target(); }',
            'function target() {}\nfunction entry() { for (let target of values) target(); }',
            'function target() {}\nconst entry = function target() { return target(); };',
            'function target() {}\nvar target = () => 2;\nfunction entry() { return target(); }',
            'function target() {}\nfunction mutate() { for (target of values) {} }\nfunction entry() { return target(); }',
            'if (true) { function target() {} }\nfunction entry() { return target(); }',
            'function target() {}\nif (true) { function entry() { return target(); } }',
            'function target() {}\nfunction outer() { function entry() { return target(); } }',
            'function target() {}\nclass Box { entry() { return target(); } }',
            'function target() {}\nfunction entry() { items.map(() => target()); return obj.target(); }',
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source in cases:
                (root / 'a.js').write_text(source)
                with self.subTest(source=source):
                    self.assertEqual(build_index(root, languages=('javascript',)).call_edges, [])

    def test_named_default_direct_export_and_import_alias_without_multihop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'core.js').write_text('export function add() { return 1; }\nexport default () => 2;\n')
            (root / 'barrel.js').write_text("export {add} from './core.js';\n")
            (root / 'app.js').write_text("import main, {add as inc} from './core.js';\nimport {add as hop} from './barrel.js';\nexport function entry() { return inc() + main() + hop(); }\n")
            index = build_index(root, languages=('javascript',))
            self.assertEqual({(e.caller, e.callee, e.line) for e in index.call_edges},
                             {('app.js::entry', 'core.js::add', 3), ('app.js::entry', 'core.js::<default>', 3)})

    def test_unique_unselected_js_implementation_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'core.js').write_text('export function inc(v) { return v + 1; }\n')
            (root / 'app.ts').write_text(
                "import { inc } from './core.js';\nexport function entry() { return inc(1); }\n")
            selected = build_index(root, languages=('typescript',))
            self.assertEqual(selected.import_edges, [])
            self.assertEqual(selected.call_edges, [])
            mixed = build_index(root, languages=('javascript', 'typescript'))
            self.assertEqual([(e.source, e.target, e.line) for e in mixed.import_edges],
                             [('app.ts', 'core.js', 1)])
            self.assertEqual([(e.caller, e.callee, e.line) for e in mixed.call_edges],
                             [('app.ts::entry', 'core.js::inc', 2)])

    def test_type_only_export_never_exposes_runtime_function(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'core.ts').write_text(
                'function inc(v: number) { return v + 1; }\nexport type { inc };\n')
            (root / 'app.ts').write_text(
                "import { inc } from './core.js';\nexport function entry() { return inc(1); }\n")
            index = build_index(root, languages=('typescript',))
            self.assertEqual(index.parse_errors, [])
            self.assertIn('core.ts::inc', index.symbols)
            self.assertEqual([(e.exported, e.local_name, e.type_only, e.start_line)
                              for e in index.esm_exports if e.file == 'core.ts'],
                             [('inc', 'inc', True, 2)])
            self.assertEqual([(e.source, e.target, e.line) for e in index.import_edges],
                             [('app.ts', 'core.ts', 1)])
            self.assertEqual(index.call_edges, [])

    def test_namespace_member_never_guesses_named_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'core.js').write_text('export function target() { return 1; }\n')
            (root / 'app.js').write_text(
                "import * as ns from './core.js';\nexport function entry() { return ns.target(); }\n")
            index = build_index(root, languages=('javascript',))
            self.assertEqual([(e.source, e.target, e.line) for e in index.import_edges],
                             [('app.js', 'core.js', 1)])
            self.assertEqual(index.call_edges, [])
            self.assertTrue(any(l.file == 'app.js' and l.line == 2 and
                                l.reason == 'unresolved-call' for l in index.analysis_limits))

    def test_extensionless_directory_index_stays_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'dir').mkdir()
            (root / 'dir/index.ts').write_text('export function target() { return 1; }\n')
            (root / 'app.ts').write_text(
                "import {target} from './dir';\nexport function entry() { return target(); }\n")
            index = build_index(root, languages=('typescript',))
            self.assertEqual(index.import_edges, [])
            self.assertEqual(index.call_edges, [])
            limits = {(l.file, l.line, l.reason) for l in index.analysis_limits}
            self.assertIn(('app.ts', 1, 'ambiguous-or-unsupported-local-source'), limits)
            self.assertIn(('app.ts', 2, 'unresolved-call'), limits)

    def test_alias_and_node_modules_stay_external(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'node_modules/pkg').mkdir(parents=True)
            (root / 'node_modules/pkg/core.js').write_text('export function target() {}\n')
            (root / 'core.js').write_text('export function target() {}\n')
            (root / 'app.js').write_text(
                "import {target} from '@alias/core';\nexport function entry() { return target(); }\n")
            index = build_index(root, languages=('javascript',))
            self.assertEqual({f.path for f in index.files}, {'app.js', 'core.js'})
            self.assertEqual(index.import_edges, [])
            self.assertEqual(index.call_edges, [])
            limits = {(l.file, l.line, l.reason) for l in index.analysis_limits}
            self.assertIn(('app.js', 1, 'external-or-alias'), limits)
            self.assertIn(('app.js', 2, 'unresolved-call'), limits)
