"""Source dialects preserve exact evidence and reject all recovered error trees."""
from pathlib import Path
import tempfile
import unittest

from tests.test_js_ts import HAS_EXTRA


@unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
class RecoveredTreeTests(unittest.TestCase):
    def test_anonymous_missing_tokens_exclude_all_partial_evidence(self):
        from repo_doctor.js_ts import extract
        sources = [
            ('truncated.js', 'javascript',
             'export function target() { return 1; }\n'
             'export function broken() {\n  return target();\n', 3),
            ('call.ts', 'typescript',
             'export function target() { return 1; }\n'
             'export function broken() { return target(; }\n', 2),
        ]
        for file, language, source, line in sources:
            with self.subTest(file=file):
                data = extract(source, file=file, language=language)
                self.assertIsNotNone(data['error'])
                self.assertEqual((data['error']['file'], data['error']['line']), (file, line))
                for key in ('symbols', 'esm_imports', 'esm_exports', 'calls',
                            'identifier_uses', 'top_level_symbols', 'unsafe_bindings', 'limits'):
                    self.assertEqual(data[key], [], key)
                self.assertEqual(data['class_header_spans'], {})

    def test_missing_token_target_cannot_create_import_or_call_edges(self):
        from repo_doctor.index import build_index
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'bad.js').write_text(
                'export function target() { return 1; }\n'
                'export function broken() {\n  return target();\n')
            (root / 'consumer.js').write_text(
                "import {target} from './bad.js';\n"
                'export function entry() { return target(); }\n')
            index = build_index(root, languages=('javascript',))
            self.assertEqual([(e.file, e.line) for e in index.parse_errors], [('bad.js', 3)])
            self.assertEqual(set(index.symbols), {'consumer.js::entry'})
            self.assertEqual(index.import_edges, [])
            self.assertEqual(index.call_edges, [])
            self.assertFalse(any(r.file == 'bad.js' for r in index.esm_imports))
            self.assertFalse(any(r.file == 'bad.js' for r in index.esm_exports))


@unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
class FrontendDialectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def write(self, files):
        for name, source in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding='utf-8')

    def frontend_index(self):
        from repo_doctor.index import build_index
        self.write({
            'helper.ts': 'export function value() { return 1; }\n',
            'Card.tsx': 'export function Card() { return <div />; }\n',
            'App.tsx': "import {value} from './helper.js';\nimport {Card} from './Card';\n"
                       'export function App() { return <Card onClick={() => value()}>{value()}</Card>; }\n',
            'Legacy.jsx': 'export const Legacy = () => <section>中文😀</section>;\n',
        })
        return build_index(self.root, languages=('javascript', 'typescript'))

    def test_selected_frontend_extensions_and_scope_are_explicit(self):
        from repo_doctor.languages import language_for_path, analysis_metadata
        self.assertEqual(language_for_path('App.tsx'), 'typescript')
        self.assertEqual(language_for_path('Legacy.jsx'), 'javascript')
        index = self.frontend_index()
        self.assertEqual(index.parse_errors, [])
        self.assertEqual({f.path for f in index.files}, {'helper.ts', 'Card.tsx', 'App.tsx', 'Legacy.jsx'})
        self.assertEqual(set(index.symbols), {'helper.ts::value', 'Card.tsx::Card', 'App.tsx::App', 'Legacy.jsx::Legacy'})
        self.assertEqual(analysis_metadata(index)['source_extensions'], {
            'javascript': ['.js', '.mjs', '.jsx'], 'typescript': ['.ts', '.tsx']})
        self.assertFalse(any(l.reason == 'unsupported-source-kind' and l.file.endswith(('.jsx', '.tsx'))
                             for l in index.analysis_limits))

    def test_jsx_tags_handlers_and_callbacks_do_not_create_false_calls(self):
        index = self.frontend_index()
        self.assertEqual([(e.caller, e.callee, e.line) for e in index.call_edges],
                         [('App.tsx::App', 'helper.ts::value', 3)])
        self.assertEqual({(e.source, e.target, e.line) for e in index.import_edges},
                         {('App.tsx', 'helper.ts', 1), ('App.tsx', 'Card.tsx', 2)})
        self.assertTrue(any(l.file == 'App.tsx' and l.line == 3 and l.reason == 'jsx-render'
                            for l in index.analysis_limits))
        self.assertTrue(any(l.reason == 'anonymous-callback' for l in index.analysis_limits))

    def test_frontend_context_and_impact_prove_the_actual_import(self):
        from repo_doctor.context import build_context, build_impact
        index = self.frontend_index()
        context = build_context(index, 'App.tsx::App', include_symbols=['helper.ts::value'], max_lines=120)
        edge = context['call_evidence'][0]
        self.assertEqual((edge['caller'], edge['callee'], edge['line']), ('App.tsx::App', 'helper.ts::value', 3))
        self.assertEqual(edge['via_esm_import'], {
            'file': 'App.tsx', 'specifier': './helper.js', 'imported': 'value', 'alias': 'value',
            'start_line': 1, 'end_line': 1, 'type_only': False, 'resolved_file': 'helper.ts',
            'resolution_kind': 'unique-local-source'})
        for block in context['blocks']:
            lines = (self.root / block['file']).read_text().splitlines()
            for line in block['lines']:
                self.assertEqual(line['text'], lines[line['line'] - 1])
        self.assertLessEqual(sum(len(b['lines']) for b in context['blocks']), 120)
        self.assertFalse(context['budget_exhausted'])
        self.assertTrue(all(not b['truncated'] for b in context['blocks']))
        impact = build_impact(index, 'helper.ts::value', depth=2)
        self.assertEqual([r['symbol'] for r in impact['affected_symbols']], ['App.tsx::App'])
        self.assertEqual(impact['affected_symbols'][0]['call_path_evidence'], [edge])
        self.assertEqual(build_impact(index, 'Card.tsx::Card')['affected_symbols'], [])

    def test_frontend_map_and_svg_only_project_real_evidence(self):
        from repo_doctor.repo_map import write_map
        import json
        import xml.etree.ElementTree as ET
        index = self.frontend_index()
        with tempfile.TemporaryDirectory() as output:
            out = Path(output) / 'map'
            write_map(index, out)
            self.assertEqual({p.name for p in out.iterdir()}, {'map.json', 'map.html', 'structure.svg', 'relations.svg'})
            data = json.loads((out / 'map.json').read_text())
            self.assertEqual(data['limits'], {'nodes': 200, 'edges': 500})
            self.assertEqual({(e['source'], e['target']) for e in data['edges'] if e['kind'] == 'call'},
                             {('symbol:App.tsx::App', 'symbol:helper.ts::value')})
            self.assertIn('symbol:Legacy.jsx::Legacy', {n['id'] for n in data['nodes']})
            for name, view in data['views'].items():
                svg = ET.parse(out / (name + '.svg'))
                actual = {p.get('data-edge-id') for p in svg.findall('.//{http://www.w3.org/2000/svg}path')
                          if p.get('data-edge-id') is not None}
                self.assertEqual(actual, {e['id'] for e in view['edges']})

    def test_ts_and_tsx_grammars_never_fallback_into_each_other(self):
        from repo_doctor.js_ts import extract, parse_tree
        source = 'export const pick = <T>(value: T) => value;\n'
        self.assertIsNone(extract(source, file='generic.ts', language='typescript')['error'])
        assertion = 'export function cast(value: unknown) { return <number>value; }\n'
        self.assertIsNone(extract(assertion, file='cast.ts', language='typescript')['error'])
        self.assertIsNotNone(extract(assertion, file='cast.tsx', language='typescript')['error'])
        _, tree = parse_tree('export const View = () => <div />;', 'typescript', tsx=True)
        self.assertFalse(tree.root_node.has_error)
        with self.assertRaises(ValueError):
            parse_tree('const value = 1;', 'javascript', tsx=True)

    def test_bom_unicode_crlf_frontend_context_has_exact_physical_lines(self):
        from repo_doctor.js_ts import parse_js_ts_file
        from repo_doctor.context import build_context
        from repo_doctor.index import build_index
        source = '// 中文😀\r\nexport const View = () => (\r\n  <div>你好</div>\r\n);\r\n'
        for file in ('view.tsx', 'view.jsx'):
            with self.subTest(file=file):
                (self.root / file).write_bytes(source.encode('utf-8-sig'))
                parsed = parse_js_ts_file(self.root, file)
                self.assertIsNone(parsed.parsed.error)
                symbol = parsed.parsed.symbols[0]
                self.assertEqual((symbol.id, symbol.start_line, symbol.end_line), (file + '::View', 2, 4))
                index = build_index(self.root, languages=('javascript', 'typescript'))
                block = build_context(index, symbol.id)['blocks'][0]
                self.assertEqual(block['lines'], [{'line': i, 'text': line}
                    for i, line in enumerate(source.splitlines(), 1) if 2 <= i <= 4])

    def test_default_python_and_unselected_frontend_never_read_invalid_source(self):
        from repo_doctor.index import build_index
        from repo_doctor.languages import analysis_metadata
        self.write({'app.py': 'def entry(): return 1\n'})
        (self.root / 'bad.tsx').write_bytes(b'\xff')
        (self.root / 'bad.jsx').write_bytes(b'\xff')
        index = build_index(self.root)
        self.assertEqual({f.path for f in index.files}, {'app.py'})
        self.assertEqual(index.parse_errors, [])
        self.assertNotIn('source_extensions', analysis_metadata(index))
        index = build_index(self.root, languages=('javascript',))
        self.assertEqual({f.path for f in index.files}, {'bad.jsx'})
        self.assertEqual([r.file for r in index.parse_errors], ['bad.jsx'])
        self.assertEqual(analysis_metadata(index)['source_extensions'], {'javascript': ['.js', '.mjs', '.jsx']})

    def test_tsx_js_substitution_and_extensionless_index_keep_ambiguity_guards(self):
        from repo_doctor.index import build_index
        self.write({'dir/index.tsx': 'export function value() { return <div />; }\n',
                    'caller.tsx': "import {value} from './dir/index.js';\n"
                                  'export function run() { return value(); }\n',
                    'index.tsx': "import {value} from './dir';\n"
                                 'export function run() { return value(); }\n'})
        index = build_index(self.root, languages=('typescript',))
        self.assertEqual({(e.caller, e.callee) for e in index.call_edges},
                         {('caller.tsx::run', 'dir/index.tsx::value'), ('index.tsx::run', 'dir/index.tsx::value')})
        self.write({'dir/index.d.ts': 'export declare function value(): unknown;\n'})
        index = build_index(self.root, languages=('typescript',))
        self.assertEqual(index.import_edges, [])
        self.assertEqual(index.call_edges, [])

    def test_type_namespace_shadow_and_reexport_boundaries_hold_for_frontend(self):
        from repo_doctor.index import build_index
        self.write({'leaf.tsx': 'export function value() { return <span />; }\n',
                    'barrel.tsx': "export {value} from './leaf';\n",
                    'types.tsx': "import type {value} from './leaf';\nexport function run() { return value(); }\n",
                    'namespace.tsx': "import * as ns from './leaf';\nexport function run() { return ns.value(); }\n",
                    'shadow.tsx': "import {value} from './leaf';\nexport function run(value) { return value(); }\n",
                    'hop.tsx': "import {value} from './barrel';\nexport function run() { return value(); }\n"})
        index = build_index(self.root, languages=('typescript',))
        self.assertEqual(len(index.import_edges), 5)
        self.assertEqual(index.call_edges, [])
