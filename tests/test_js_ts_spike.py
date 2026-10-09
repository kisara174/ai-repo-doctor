"""Source positions and conservative boundaries of the disposable parser."""

from pathlib import Path
import subprocess
import sys
import tempfile
import json
import importlib.util
import xml.etree.ElementTree as ET
import unittest

from experiments.js_ts.spike import extract, build_spike, context, experiment_map


FIXTURES = Path(__file__).parent / 'fixtures/js_ts_contract'


@unittest.skipUnless(all(importlib.util.find_spec(name) is not None for name in
                         ('tree_sitter', 'ai_repo_doctor_grammars', 'tree_sitter_typescript')),
                     'A3 experiment requires the isolated optional parser environment')
class SpikeContractTests(unittest.TestCase):
    def test_large_source_position_access_does_not_crash_native_backend(self):
        code = "from experiments.js_ts.spike import extract; s=''.join('function f%d(x) {\\n return x;\\n}\\n' % i for i in range(300)); d=extract(s,file='large.js',language='javascript'); print(len(d['symbols']),d['symbols'][-1]['end_line'])"
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '300 900')

    def parse(self, name):
        return extract((FIXTURES / name).read_text(), file=name,
                       language='typescript' if name.endswith('.ts') else 'javascript')

    def test_named_arrow_class_method_and_default_spans(self):
        data = self.parse('core.js')
        actual = {s['id']: (s['start_line'], s['end_line'], s['parent']) for s in data['symbols']}
        self.assertEqual(actual, {
            'core.js::add': (1, 3, None), 'core.js::twice': (4, 4, None),
            'core.js::Box': (5, 7, None), 'core.js::Box.get': (6, 6, 'core.js::Box'),
            'core.js::main': (8, 10, None)})
        self.assertIsNone(data['error'])

    def test_overloads_merge_into_one_implementation(self):
        data = self.parse('core.ts')
        overloads = [s for s in data['symbols'] if s['name'] == 'overloaded']
        self.assertEqual(len(overloads), 1)
        self.assertEqual((overloads[0]['start_line'], overloads[0]['end_line']), (9, 11))
        self.assertEqual([(o['start_line'], o['end_line']) for o in overloads[0]['overloads']], [(7, 7), (8, 8)])

    def test_syntax_error_never_leaks_partial_symbols_or_edges(self):
        data = extract('export function valid() {}\nexport function broken( {', file='bad.js', language='javascript')
        self.assertIsNotNone(data['error'])
        for name in ('symbols', 'esm_imports', 'esm_exports', 'calls'):
            self.assertEqual(data[name], [])

    def test_esm_alias_and_type_only_are_distinct(self):
        item = self.parse('consumer.ts')['esm_imports'][0]
        self.assertEqual((item['specifier'], item['imported'], item['alias'], item['type_only']), ('./core.js', 'inc', 'step', False))
        self.assertTrue(self.parse('type_only.ts')['esm_imports'][0]['type_only'])
        data = extract("import {type A, b as c} from './a.js';\nexport {c as renamed};", file='types.ts', language='typescript')
        self.assertEqual([(i['imported'], i['alias'], i['type_only']) for i in data['esm_imports']], [('A', 'A', True), ('b', 'c', False)])
        self.assertEqual(data['esm_exports'][0]['exported'], 'renamed')

    def test_comments_do_not_create_imports_or_symbols(self):
        data = extract("/**\nimport {fake} from './fake.js';\nfunction example() {}\n*/\nexport function real() {}", file='doc.ts', language='typescript')
        self.assertEqual(data['esm_imports'], [])
        self.assertEqual([s['name'] for s in data['symbols']], ['real'])

    def test_duplicate_implementations_remain_ambiguous(self):
        data = self.parse('duplicate.ts')
        self.assertEqual([s['id'] for s in data['symbols']], ['duplicate.ts::same', 'duplicate.ts::same'])
        self.assertTrue(any(l['reason'] == 'ambiguous-symbol' for l in data['limits']))

    def test_callbacks_have_no_fake_symbols_or_outer_call_ownership(self):
        source = 'function outer() { function nested() {} items.map(() => nested()); nested(); }\nexport default function() {}'
        data = extract(source, file='nested.js', language='javascript')
        self.assertEqual([s['qualname'] for s in data['symbols']], ['outer', 'outer.nested', '<default>'])
        calls = [c for c in data['calls'] if c['name'] == 'nested']
        self.assertEqual([c['caller'] for c in calls], [None, 'nested.js::outer'])

    def test_unicode_crlf_and_bom_keep_human_line_positions(self):
        data = extract('\ufeff// 中文😀\r\nexport function café() {\r\n return 1;\r\n}', file='unicode.js', language='javascript')
        self.assertEqual([(s['name'], s['start_line'], s['end_line']) for s in data['symbols']], [('café', 2, 4)])

    def test_type_asserted_method_alias_is_not_a_function_definition(self):
        data = extract('export const objectEntries = Object.entries as <T>(x: T) => unknown;', file='alias.ts', language='typescript')
        self.assertEqual(data['symbols'], [])

    def test_parameters_locals_and_rewrites_are_recorded_conservatively(self):
        data = extract('function f({a = 1}, ...rest) { const local=1; try {} catch(error) {} a++; return local; }', file='bindings.js', language='javascript')
        self.assertTrue({'a', 'rest', 'local', 'error'} <= set(data['symbols'][0]['local_bindings']))
        self.assertIn('a', data['unsafe_bindings'])

    def test_ts_extension_substitution_requires_a_unique_source(self):
        index, parsed, analysis, fingerprint = build_spike(FIXTURES, ('javascript', 'typescript'))
        self.assertNotIn(('consumer.ts', 'core.ts'), [(e.source, e.target) for e in index.import_edges])
        self.assertNotIn('bad.js::broken', index.symbols)
        self.assertIn('duplicate.ts::same', index.ambiguous_symbols)
        self.assertNotIn('duplicate.ts::same', index.symbols)
        self.assertFalse({'unsupported.cjs', 'unsupported.tsx', 'declarations.d.ts'} & set(parsed))
        self.assertTrue({'unsupported.cjs', 'unsupported.tsx', 'declarations.d.ts'} <=
                        {l['file'] for l in analysis['limits'] if l['reason'] == 'unsupported-source-kind'})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'core.ts').write_text('export function inc(v: number) { return v+1; }')
            (root / 'consumer.ts').write_text("import {inc} from './core.js';\nexport function run() { return inc(1); }")
            one, parsed, analysis, fingerprint = build_spike(root, ('typescript',))
            self.assertEqual([(e.source, e.target, e.line) for e in one.import_edges], [('consumer.ts', 'core.ts', 1)])
            result = context(one, parsed, 'consumer.ts::run', [], 1)
            self.assertEqual(result['used_lines'], 1)
            self.assertEqual(result['omitted_imports'], 1)
            self.assertEqual(result['blocks'][0]['relation'], 'target')
            out = root / 'output'
            experiment_map(one, parsed, analysis, fingerprint, out, None, 1)
            data = json.loads((out / 'map.json').read_text())
            files = [n for n in data['nodes'] if n['kind'] == 'file' and n['analyzed']]
            self.assertEqual({n['file'] for n in files}, {'core.ts', 'consumer.ts'})
            self.assertTrue(all(not n['python'] for n in files))
            self.assertEqual({n['file'] for n in data['views']['relations']['nodes']}, {'core.ts', 'consumer.ts'})
            for mode in ('structure', 'relations'):
                self.assertEqual(ET.parse(out / (mode + '.svg')).getroot().tag, '{http://www.w3.org/2000/svg}svg')


if __name__ == '__main__':
    unittest.main()
