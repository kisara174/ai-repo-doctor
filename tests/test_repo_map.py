import io
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from repo_doctor.cli import main


class RepoMapTests(unittest.TestCase):
    def test_unique_index_file_relations_and_type_only_boundary_reach_offline_artifacts(self):
        from tests.test_js_ts import HAS_EXTRA
        if not HAS_EXTRA:
            self.skipTest('requires optional js extra')
        (self.repo/'dir').mkdir()
        (self.repo/'dir/index.ts').write_text('export function inc() { return 1; }\n')
        (self.repo/'app.ts').write_text("import {inc} from './dir';\nexport function run() { return inc(); }\n")
        (self.repo/'types.ts').write_text("import type {inc} from './dir';\nexport function bad() { return inc(); }\n")
        status,output,err=self.generate('--languages','typescript')
        self.assertEqual(status,0,err)
        data=json.loads((output/'map.json').read_text())
        edges={(e['kind'],e['source'],e['target']):e for e in data['edges']}
        self.assertEqual(edges[('import','file:app.ts','file:dir/index.ts')]['evidence'],
                         [{'file':'app.ts','line':1}])
        self.assertIn(('import','file:types.ts','file:dir/index.ts'),edges)
        self.assertIn(('call','symbol:app.ts::run','symbol:dir/index.ts::inc'),edges)
        self.assertNotIn(('call','symbol:types.ts::bad','symbol:dir/index.ts::inc'),edges)
        self.assertIn(('call','file:app.ts','file:dir/index.ts'),
                      {(e['kind'],e['source'],e['target']) for e in data['file_edges']})
        self.assertEqual(data['limits'],{'nodes':200,'edges':500})
        self.assertFalse(data['analysis']['esm_source_resolution']['runtime_resolution'])
        ns={'s':'http://www.w3.org/2000/svg'}
        for name,view in data['views'].items():
            ids={n['id'] for n in view['nodes']}
            self.assertTrue(all(e['source'] in ids and e['target'] in ids for e in view['edges']))
            svg=ET.parse(output/(name+'.svg'))
            actual={e.get('data-edge-id') for e in svg.findall('.//s:path',ns)
                    if e.get('data-edge-id') is not None}
            self.assertEqual(actual,{e['id'] for e in view['edges']})
        self.assertTrue((output/'map.html').is_file())

    def test_mixed_relation_projection_uses_analyzed_and_preserves_legacy(self):
        from tests.test_js_ts import HAS_EXTRA, FIXTURES
        if not HAS_EXTRA:
            self.skipTest('requires optional js extra')
        import shutil
        from repo_doctor.index import build_index
        from repo_doctor.repo_map import build_map, project_view
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'repo'
            shutil.copytree(FIXTURES, root)
            (root / 'app.py').write_text('def entry():\n    return 42\n', encoding='utf-8')
            data = build_map(build_index(root, languages=('python', 'javascript', 'typescript')))
            files = {n['file']: n for n in data['nodes'] if n['kind'] == 'file'}
            for name, language in [('app.py', 'python'), ('core.js', 'javascript'), ('core.ts', 'typescript')]:
                self.assertTrue(files[name]['analyzed'])
                self.assertEqual(files[name]['language'], language)
                self.assertEqual(files[name]['python'], language == 'python')
                self.assertIn('file:' + name, {n['id'] for n in data['views']['relations']['nodes']})
            for view in data['views'].values():
                ids = {n['id'] for n in view['nodes']}
                self.assertTrue(all(e['source'] in ids and e['target'] in ids for e in view['edges']))
            self.assertFalse(any(e['source'] == 'symbol:consumer.ts::run' and e['target'] == 'symbol:core.ts::inc' for e in data['edges']))
            self.assertEqual(data['coverage']['python_files'], 1)
            self.assertFalse(any(l['reason'] == 'map-projection-pending' for l in data['analysis']['limits']))
            for node in data['nodes']:
                node.pop('analyzed', None)
            legacy = project_view(data, 'relations')
            self.assertEqual({n['id'] for n in legacy['nodes']}, {'file:app.py'})

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        (self.repo / 'a.py').write_text('def target():\n    return 1\n')
        (self.repo / 'b.py').write_text('from a import target\n\ndef run():\n    return target()\n')
        (self.repo / 'README.md').write_text('Do not embed private source contents')
        (self.repo / 'test_a.py').write_text('from a import target\ndef test_it(): return target()\n')

    def generate(self, *extra, destination=None):
        output = destination or self.base / 'map'
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                status = main(['map', str(self.repo), '--out', str(output), '--json', *extra])
            except SystemExit as exc:
                status = exc.code
        return status, output, stderr.getvalue()

    def test_map_projects_exact_relations_and_metadata_without_file_contents(self):
        status, output, err = self.generate()
        self.assertEqual(status, 0, err)
        data = json.loads((output / 'map.json').read_text())
        ids = {node['id'] for node in data['nodes']}
        self.assertTrue({'dir:.', 'file:README.md', 'file:a.py', 'symbol:a.py::target'} <= ids)
        edges = [(edge['kind'], edge['source'], edge['target']) for edge in data['edges']]
        self.assertIn(('call', 'symbol:b.py::run', 'symbol:a.py::target'), edges)
        self.assertIn(('import', 'file:b.py', 'file:a.py'), edges)
        call = next(edge for edge in data['edges'] if edge['kind'] == 'call' and edge['source'] == 'symbol:b.py::run')
        self.assertEqual(call['evidence'], [{'file': 'b.py', 'line': 4}])
        self.assertNotIn('Do not embed private source contents', (output / 'map.json').read_text())
        self.assertNotIn('file:test_a.py', [node['id'] for node in data['views']['relations']['nodes']])
        self.assertIn('file:b.py', [node['id'] for node in data['views']['relations']['nodes']])

    def test_focused_map_contains_direct_caller_without_inventing_unknown_calls(self):
        (self.repo / 'dynamic.py').write_text('def dynamic(obj):\n    return obj.unknown()\n')
        status, output, err = self.generate('--symbol', 'a.py::target', '--depth', '1')
        self.assertEqual(status, 0, err)
        data = json.loads((output / 'map.json').read_text())
        self.assertEqual(data['coverage']['unresolved_calls'], 1)
        ids = {node['id'] for node in data['views']['relations']['nodes']}
        self.assertEqual(ids, {'symbol:a.py::target', 'symbol:b.py::run', 'file:b.py'})
        self.assertTrue(any(edge['kind'] == 'reexport' and edge['source'] == 'file:b.py'
                            for edge in data['views']['relations']['edges']))

    def test_view_limit_reports_hidden_nodes_and_never_leaves_dangling_edges(self):
        for number in range(210):
            (self.repo / f'm{number:03}.py').write_text('x = 1\n')
        status, output, err = self.generate()
        self.assertEqual(status, 0, err)
        data = json.loads((output / 'map.json').read_text())
        for view in data['views'].values():
            ids = {node['id'] for node in view['nodes']}
            self.assertLessEqual(len(ids), 200)
            self.assertGreater(view['hidden_nodes'], 0)
            self.assertTrue(all(edge['source'] in ids and edge['target'] in ids for edge in view['edges']))

    def test_default_structure_is_a_collapsed_project_overview(self):
        (self.repo / 'pkg').mkdir()
        (self.repo / 'pkg' / 'module.py').write_text('def inside(): return 1\n')
        status, output, err = self.generate()
        self.assertEqual(status, 0, err)
        data = json.loads((output / 'map.json').read_text())
        ids = {node['id'] for node in data['views']['structure']['nodes']}
        self.assertIn('dir:pkg', ids)
        self.assertNotIn('file:pkg/module.py', ids)
        self.assertIn('file:pkg/module.py', {node['id'] for node in data['nodes']})

    def test_map_does_not_follow_symlinks_or_replace_an_existing_directory(self):
        secret = self.base / 'external.py'
        secret.write_text('def external(): return 1\n')
        (self.repo / 'linked.py').symlink_to(secret)
        status, output, err = self.generate()
        self.assertEqual(status, 0, err)
        self.assertNotIn('file:linked.py', {node['id'] for node in json.loads((output / 'map.json').read_text())['nodes']})
        before = (output / 'map.json').read_bytes()
        status, _, err = self.generate(destination=output)
        self.assertEqual(status, 2)
        self.assertEqual((output / 'map.json').read_bytes(), before)

    def test_offline_bundle_preserves_labels_and_escapes_untrusted_text(self):
        (self.repo / 'odd<&>.py').write_text('x = 1\n')
        status, output, err = self.generate()
        self.assertEqual(status, 0, err)
        for filename in ('map.html', 'structure.svg', 'relations.svg'):
            self.assertTrue((output / filename).is_file(), filename)
        namespace = {'s': 'http://www.w3.org/2000/svg'}
        structure = ET.parse(output / 'structure.svg')
        labels = [element.text for element in structure.findall('.//s:text', namespace)]
        self.assertIn('odd<&>.py', labels)
        relations = ET.parse(output / 'relations.svg')
        edge_ids = {element.get('data-edge-id') for element in relations.findall('.//s:path', namespace)}
        data = json.loads((output / 'map.json').read_text())
        self.assertTrue({edge['id'] for edge in data['views']['relations']['edges']} <= edge_ids)
        class PageParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_data = False
                self.data = ''
                self.external = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'script' and attrs.get('id') == 'map-data':
                    self.in_data = True
                if tag == 'script' and attrs.get('src'):
                    self.external.append(attrs['src'])
            def handle_endtag(self, tag):
                if tag == 'script':
                    self.in_data = False
            def handle_data(self, value):
                if self.in_data:
                    self.data += value
        parser = PageParser()
        parser.feed((output / 'map.html').read_text())
        self.assertEqual(parser.external, [])
        self.assertEqual(json.loads(parser.data)['repository'], data['repository'])
        self.assertNotIn('<', parser.data)


if __name__ == '__main__':
    unittest.main()
