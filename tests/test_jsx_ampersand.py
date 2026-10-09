"""JSX attributes use original bytes; malformed files still yield no evidence."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.test_js_ts import HAS_EXTRA


@unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
class JSXAttributeTests(unittest.TestCase):
    def test_incompatible_companion_is_rejected_without_parser_fallback(self):
        from repo_doctor import js_ts
        installed_version = js_ts.version
        def incompatible(name):
            return '0.0.0' if name == 'ai-repo-doctor-grammars' else installed_version(name)
        js_ts._parser.cache_clear()
        try:
            with mock.patch.object(js_ts, 'version', side_effect=incompatible):
                with self.assertRaisesRegex(ValueError, 'backend unavailable or incompatible'):
                    js_ts.parse_tree('export function valid() {}', 'javascript')
        finally:
            js_ts._parser.cache_clear()

    def test_url_attributes_restore_exact_symbols_calls_and_source(self):
        from repo_doctor.index import build_index
        from repo_doctor.context import build_context
        for suffix in ('.js', '.jsx', '.tsx'):
            for quote in ('"', "'"):
                with self.subTest(suffix=suffix, quote=quote), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory).resolve()
                    helper = 'helper.ts' if suffix == '.tsx' else 'helper.js'
                    (root / helper).write_text('export function helper() { return 1; }\n')
                    source = ('// 中文😀\r\n'
                              f'import {{helper}} from "./{helper}";\r\n'
                              'export const View = () => (\r\n'
                              f'  <img src={quote}?a=1&emoji=&slug=中文😀&{quote} alt={{helper()}} />\r\n'
                              ');\r\n')
                    name = 'View' + suffix
                    (root / name).write_bytes(source.encode('utf-8'))
                    before = (root / name).read_bytes()
                    index = build_index(root, languages=('javascript', 'typescript'))
                    self.assertEqual(index.parse_errors, [])
                    symbol = index.symbols[name + '::View']
                    self.assertEqual((symbol.start_line, symbol.end_line), (3, 5))
                    self.assertEqual([(e.caller, e.callee, e.line) for e in index.call_edges],
                                     [(name + '::View', helper + '::helper', 4)])
                    context = build_context(index, symbol.id, max_lines=120)
                    lines = source.replace('\r\n', '\n').split('\n')
                    for block in context['blocks']:
                        if block['file'] == name:
                            for line in block['lines']:
                                self.assertEqual(line['text'], lines[line['line'] - 1])
                    self.assertEqual((root / name).read_bytes(), before)

    def test_valid_entities_and_plain_ampersands_are_parsed_without_recovery(self):
        from repo_doctor.js_ts import parse_tree
        for language, tsx in (('javascript', False), ('typescript', True)):
            for value in ('&', 'a&b', 'a& b', '&amp;', '&#38;', '&#x26;', 'a&unknown;'):
                with self.subTest(language=language, value=value):
                    raw, tree = parse_tree(f'const View = () => <img src="{value}" />;', language, tsx=tsx)
                    self.assertFalse(tree.root_node.has_error)
                    self.assertEqual(tree.root_node.end_byte, len(raw))

    def test_real_syntax_errors_after_valid_attributes_exclude_all_evidence(self):
        from repo_doctor.js_ts import extract
        for file, language in (('bad.js', 'javascript'), ('bad.tsx', 'typescript')):
            for tail in ('export function broken() {\n',
                         'export function broken() { return helper(; }\n',
                         'export const broken = () => <img src="?x=1&b=2 />;\n'):
                with self.subTest(file=file, tail=tail):
                    data = extract('export const View = () => <img src="?a=1&b=2" />;\n' + tail,
                                   file=file, language=language)
                    self.assertIsNotNone(data['error'])
                    for key in ('symbols', 'calls', 'esm_imports', 'esm_exports', 'identifier_uses',
                                'top_level_symbols', 'unsafe_bindings', 'limits'):
                        self.assertEqual(data[key], [], key)
                    self.assertEqual(data['class_header_spans'], {})

    def test_jsx_text_ampersand_and_flow_are_not_newly_supported(self):
        from repo_doctor.js_ts import extract
        for source in ('export const View = () => <div>Shipping & Handling</div>;\n',
                       'type Value = {|name: string|};\nexport const value: Value = {name:"x"};\n'):
            with self.subTest(source=source):
                result = extract(source, file='unsupported.js', language='javascript')
                self.assertIsNotNone(result['error'])
                self.assertEqual(result['symbols'], [])
