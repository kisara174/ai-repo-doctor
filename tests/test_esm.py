"""Finite ESM file resolution never guesses ambiguous or excluded sources."""

from pathlib import Path
import tempfile
import unittest

from repo_doctor.index import build_index
from tests.test_js_ts import HAS_EXTRA


@unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
class SourceAssociationTests(unittest.TestCase):
    def make_index(self, root, specifier, files, *, languages=('javascript', 'typescript'),
                   consumer=None, app='app.ts'):
        for filename, source in files.items():
            path = root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding='utf-8')
        path = root / app
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(consumer or f"import {{inc}} from '{specifier}';\n"
                        'export function run() { return inc(); }\n', encoding='utf-8')
        return build_index(root, languages=languages)

    def test_unique_file_index_and_normalized_parent_preserve_safe_calls(self):
        source = 'export function inc() { return 1; }\n'
        cases = [('./core', 'core'+ext, 'app.ts', 'unique-extensionless-source')
                 for ext in ('.js', '.ts', '.mjs')]
        cases += [('./dir', 'dir/index'+ext, 'app.ts', 'unique-directory-index-source')
                  for ext in ('.js', '.ts')]
        cases += [('../core', 'core.ts', 'nested/app.ts', 'unique-extensionless-source'),
                  ('../.', 'index.ts', 'nested/app.ts', 'unique-directory-index-source')]
        for specifier, target, app, kind in cases:
            with self.subTest(specifier=specifier, target=target), tempfile.TemporaryDirectory() as d:
                index = self.make_index(Path(d).resolve(), specifier, {target: source}, app=app)
                self.assertEqual([(r.resolved_file,r.resolution_kind) for r in index.esm_imports],
                                 [(target,kind)])
                self.assertEqual([(e.source,e.target,e.line) for e in index.import_edges], [(app,target,1)])
                self.assertEqual([(e.caller,e.callee,e.line) for e in index.call_edges],
                                 [(app+'::run',target+'::inc',2)])

    def test_ambiguity_includes_unselected_unsupported_exact_and_index_candidates(self):
        source = 'export function inc() { return 1; }\n'
        cases = [('./core', ['core.ts','core.js']), ('./core',['core.ts','core.d.ts']),
                 ('./dir',['dir.ts','dir/index.ts']), ('./core',['core','core.ts']),
                 ('./dir',['dir/index.ts','dir/index.tsx']),
                 ('./core',['core.ts','core.json']), ('./core',['core.ts','core.node'])]
        for specifier, candidates in cases:
            with self.subTest(candidates=candidates), tempfile.TemporaryDirectory() as d:
                index = self.make_index(Path(d).resolve(), specifier,
                                        {p:source for p in candidates}, languages=('typescript',))
                self.assertEqual(index.import_edges, [])
                self.assertEqual(index.call_edges, [])
                self.assertIn('ambiguous-local-source-candidates', {r.reason for r in index.analysis_limits})

    def test_missing_ineligible_parse_failed_configured_and_special_paths_are_refused(self):
        source = 'export function inc() { return 1; }\n'
        cases = [('./core', {}, 'no-local-source-candidate'),
                 ('./core', {'core.js':source}, 'unselected-or-unsupported-local-source'),
                 ('./core', {'core.ts':'export function broken( {\n'}, 'parse-error-local-source'),
                 ('./dir', {'dir/index.ts':source,'dir/package.json':'{}'}, 'directory-package-configuration'),
                 ('./core', {'core.ts':source,'core/package.json':'{}'}, 'directory-package-configuration'),
                 ('../../../outside', {}, 'outside-source-root')]
        cases += [('./core', {'core'+ext:source}, 'unselected-or-unsupported-local-source')
                  for ext in ('.d.ts','.jsx','.mts','.cts','.cjs','.d.mts','.d.cts','.json','.node')]
        cases += [(spec, {'core.ts':source}, 'unsupported-source-specifier')
                  for spec in ('./core?x','./core#x','./core%x','./core/')]
        for specifier, files, reason in cases:
            with self.subTest(specifier=specifier, files=list(files)), tempfile.TemporaryDirectory() as d:
                index = self.make_index(Path(d).resolve(), specifier, files, languages=('typescript',))
                self.assertEqual(index.import_edges, [])
                self.assertEqual(index.call_edges, [])
                self.assertIn(reason, {r.reason for r in index.analysis_limits})

    def test_new_file_dependencies_do_not_relax_type_namespace_shadow_or_reexport_calls(self):
        cases = ["import type {inc} from './core';\nexport function run() { return inc(); }\n",
                 "import * as ns from './core';\nexport function run() { return ns.inc(); }\n",
                 "import {inc} from './core';\nexport function run(inc) { return inc(); }\n",
                 "import {inc} from './core';\ninc = replacement;\nexport function run() { return inc(); }\n",
                 "import {inc} from './core';\nexport function run() { return [1].map(() => inc()); }\n",
                 "import {inc} from './barrel';\nexport function run() { return inc(); }\n"]
        for consumer in cases:
            with self.subTest(consumer=consumer), tempfile.TemporaryDirectory() as d:
                index = self.make_index(Path(d).resolve(), './core',
                    {'core.ts':'export function inc() { return 1; }\n',
                     'barrel.ts':"export {inc} from './core';\n"}, consumer=consumer)
                self.assertTrue(index.import_edges)
                self.assertEqual(index.call_edges, [])

    def test_ignored_generated_and_symlink_targets_are_not_read(self):
        import subprocess
        for target in ('core.ts', 'node_modules/core.ts', 'build/core.ts', 'linked.ts'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as d:
                root = Path(d).resolve() / 'repo'
                root.mkdir()
                subprocess.run(['git','init','-q',str(root)], check=True, capture_output=True)
                if target == 'core.ts':
                    (root/'.gitignore').write_text('core.ts\n')
                if target == 'linked.ts':
                    outside = Path(d)/'outside.ts'
                    outside.write_text('export function inc() {}')
                    (root/target).symlink_to(outside)
                    files = {}
                else:
                    files = {target:'export function inc() {}'}
                index = self.make_index(root, './'+target[:-3], files)
                self.assertEqual(index.import_edges, [])
                self.assertEqual(index.call_edges, [])

    def test_repeated_bindings_resolve_once_and_repeated_graph_has_no_duplicates(self):
        from unittest.mock import patch
        from repo_doctor.esm import _resolve_source, resolve_esm_graph
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root/'core.ts').write_text('export function inc() {}\nexport function dec() {}\n')
            (root/'app.ts').write_text("import {inc,dec} from './core';\nexport {inc} from './core';\n"
                                       'export function run() { inc(); dec(); missing(); }\n')
            with patch('repo_doctor.esm._resolve_source', wraps=_resolve_source) as resolver:
                index = build_index(root, languages=('typescript',))
            self.assertEqual(resolver.call_count, 1, 'work must scale by declaration path, not binding count')
            before = (list(index.import_edges),list(index.call_edges),list(index.analysis_limits))
            resolve_esm_graph(index)
            self.assertEqual((index.import_edges,index.call_edges,index.analysis_limits), before)


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
            self.assertIn(('app.ts', 'core.ts', 3), [(e.source, e.target, e.line) for e in index.import_edges])
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

    def test_extensionless_directory_index_resolves_unique_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'dir').mkdir()
            (root / 'dir/index.ts').write_text('export function target() { return 1; }\n')
            (root / 'app.ts').write_text(
                "import {target} from './dir';\nexport function entry() { return target(); }\n")
            index = build_index(root, languages=('typescript',))
            self.assertEqual([(e.source,e.target,e.line) for e in index.import_edges],
                             [('app.ts','dir/index.ts',1)])
            self.assertEqual([(e.caller,e.callee,e.line) for e in index.call_edges],
                             [('app.ts::entry','dir/index.ts::target',2)])

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
