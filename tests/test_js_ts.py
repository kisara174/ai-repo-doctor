"""Typed parser evidence and unsupported boundaries."""

from pathlib import Path
import importlib.util
import tempfile
import unittest

FIXTURES = Path(__file__).parent / 'fixtures/js_ts_contract'
HAS_EXTRA = all(importlib.util.find_spec(name) for name in
                ('tree_sitter', 'tree_sitter_javascript', 'tree_sitter_typescript'))


@unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
class JSTests(unittest.TestCase):
    def parse(self, path):
        from repo_doctor.js_ts import parse_js_ts_file
        return parse_js_ts_file(FIXTURES.resolve(), path)

    def test_public_ids_and_exact_spans_come_from_source(self):
        data = self.parse('core.js')
        self.assertEqual({s.id: (s.start_line, s.end_line, s.parent) for s in data.parsed.symbols}, {
            'core.js::add': (1, 3, None), 'core.js::twice': (4, 4, None),
            'core.js::Box': (5, 7, None), 'core.js::Box.get': (6, 6, 'core.js::Box'),
            'core.js::main': (8, 10, None)})
        self.assertEqual(data.class_header_spans['core.js::Box'], (5, 5))
        overloaded = next(s for s in self.parse('core.ts').parsed.symbols if s.name == 'overloaded')
        self.assertEqual((overloaded.start_line, overloaded.end_line), (9, 11))
        self.assertEqual([(s.start_line, s.end_line) for s in overloaded.overloads], [(7, 7), (8, 8)])

    def test_inline_esm_comments_do_not_create_empty_names(self):
        from repo_doctor.js_ts import extract
        data = extract("import { /* doc */ f } from './a.js';\nexport { /* doc */ f };",
                       file='b.js', language='javascript')
        self.assertEqual([(r['imported'], r['alias']) for r in data['esm_imports']], [('f', 'f')])
        self.assertEqual([(r['exported'], r['local_name']) for r in data['esm_exports']], [('f', 'f')])

    def test_bad_syntax_and_bad_utf8_produce_errors_without_partial_evidence(self):
        data = self.parse('bad.js')
        self.assertIsNotNone(data.parsed.error)
        self.assertEqual(data.parsed.symbols, [])
        self.assertEqual(data.esm_imports, [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'bad.ts').write_bytes(b'export function f() {}\n\xff')
            from repo_doctor.js_ts import parse_js_ts_file
            bad = parse_js_ts_file(root, 'bad.ts')
            self.assertIsNotNone(bad.parsed.error)
            self.assertEqual(bad.parsed.symbols, [])

    def test_async_default_bindings_rewrites_and_type_aliases_are_conservative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'a.ts').write_text('export default async function() {}\nfunction f({a = 1}, ...rest) { const local=1; a++; return local; }\nexport const alias = Object.entries as <T>(x: T) => unknown;')
            from repo_doctor.js_ts import parse_js_ts_file
            data = parse_js_ts_file(root, 'a.ts')
            self.assertEqual([s.name for s in data.parsed.symbols], ['<default>', 'f'])
            self.assertTrue(data.parsed.symbols[0].is_async)
            self.assertTrue({'a', 'rest', 'local'} <= data.parsed.symbols[1].local_bindings)
            self.assertIn('a', data.unsafe_bindings)

    def test_mjs_async_default_preserves_source_span(self):
        from repo_doctor.index import build_index
        from repo_doctor.context import build_context

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'async.mjs').write_text(
                'export default async function() {\n  return 1;\n}\n', encoding='utf-8')
            index = build_index(root, languages=('javascript',))
            self.assertEqual(index.parse_errors, [])
            symbol = index.symbols['async.mjs::<default>']
            self.assertEqual((symbol.kind, symbol.is_async, symbol.start_line, symbol.end_line),
                             ('function', True, 1, 3))
            context = build_context(index, symbol.id)
            self.assertEqual(context['blocks'][0]['lines'], [
                {'line': 1, 'text': 'export default async function() {'},
                {'line': 2, 'text': '  return 1;'},
                {'line': 3, 'text': '}'},
            ])
