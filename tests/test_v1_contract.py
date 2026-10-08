"""Consumer-facing contracts for the five offline investigation commands."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from repo_doctor.cli import main


class CLIHarness:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        (self.repo / 'app.py').write_text(
            'def leaf(value):\n    return value + 1\n\n'
            'def entry(value):\n    return leaf(value)\n', encoding='utf-8')

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                status = main([str(arg) for arg in argv])
            except SystemExit as exc:
                status = exc.code
        return status, out.getvalue(), err.getvalue()

    def data(self, *argv):
        status, out, err = self.run_cli(*argv, '--json')
        self.assertEqual(status, 0, err)
        self.assertEqual(err, '')
        data = json.loads(out)
        self.assertEqual(data['resource_limits'], {
            'max_file_bytes': 2097152, 'max_total_bytes': 67108864, 'max_files': 5000,
            'git_timeout_seconds': 15, 'index_timeout_seconds': 60, 'timeout_kind': 'cooperative'})
        return data

    def symbol(self, name):
        result = self.data('symbols', self.repo, '--query', name)
        self.assertEqual(len(result['matches']), 1)
        return result['matches'][0]['id']


class CoreContractTests(CLIHarness, unittest.TestCase):
    def test_overview_is_bounded_and_python_is_the_default(self):
        (self.repo / 'ignored.js').write_text('export function other() {}')
        result = self.data('overview', self.repo)
        self.assertEqual(result['schema_version'], 1)
        self.assertEqual(result['root'], str(self.repo))
        self.assertEqual(result['stats']['python_files'], 1)
        self.assertEqual(result['stats']['symbols'], 2)
        self.assertEqual(result['stats']['resolved_calls'], 1)
        self.assertEqual(result['analysis']['requested_languages'], ['python'])
        self.assertEqual(len(result['source_fingerprint']), 64)
        self.assertLessEqual(len(result['sample_symbols']), 10)
        self.assertLessEqual(len(result['review_leads']), 5)
        self.assertEqual(result['next_commands']['symbols'][:3],
                         ['repo-doctor', 'symbols', str(self.repo)])

    def test_symbols_return_source_ids_and_one_based_physical_lines(self):
        result = self.data('symbols', self.repo, '--query', 'leaf')
        self.assertEqual(result['schema_version'], 1)
        self.assertFalse(result['candidates'])
        self.assertEqual(result['matches'], [{'id': 'app.py::leaf', 'file': 'app.py',
                          'name': 'leaf', 'qualname': 'leaf', 'kind': 'function', 'start_line': 1}])
        limited = self.data('symbols', self.repo, '--query', 'app.py', '--limit', 1)
        self.assertEqual(len(limited['matches']), 1)

    def test_context_preserves_quotes_and_reports_line_budget_exhaustion(self):
        target = self.symbol('entry')
        result = self.data('context', self.repo, target, '--max-lines', 1)
        self.assertEqual(result['schema_version'], 2)
        self.assertEqual(result['symbol'], target)
        self.assertTrue(result['budget_exhausted'])
        block = result['blocks'][0]
        self.assertTrue(block['truncated'])
        self.assertEqual(block['start_line'], 4)
        self.assertEqual(block['end_line'], 4)
        self.assertEqual(block['lines'], [{'line': 4, 'text': 'def entry(value):'}])
        self.assertEqual(sum(len(row['lines']) for row in result['blocks']), 1)
        self.assertEqual(result['call_evidence'][0]['caller'], target)
        self.assertEqual(result['call_evidence'][0]['line'], 5)
        full = self.data('context', self.repo, target, '--include-symbol', self.symbol('leaf'))
        self.assertFalse(full['budget_exhausted'])
        self.assertIn({'line': 5, 'text': '    return leaf(value)'}, full['blocks'][0]['lines'])

    def test_impact_is_reverse_calls_with_auditable_hops_not_runtime_coverage(self):
        target, caller = self.symbol('leaf'), self.symbol('entry')
        result = self.data('impact', self.repo, target, '--depth', 2)
        self.assertEqual(result['schema_version'], 2)
        self.assertEqual(result['depth'], 2)
        self.assertEqual(len(result['affected_symbols']), 1)
        affected = result['affected_symbols'][0]
        self.assertEqual(affected['symbol'], caller)
        self.assertEqual(affected['distance'], 1)
        self.assertEqual(affected['path'], [target, caller])
        self.assertEqual(affected['call_path_evidence'][0]['line'], 5)
        self.assertEqual(self.data('impact', self.repo, caller)['affected_symbols'], [])

    def test_map_writes_four_offline_artifacts_and_refuses_overwrite(self):
        destination = self.base / 'new map'
        result = self.data('map', self.repo, '--out', destination)
        self.assertEqual(result['schema_version'], 1)
        artifacts = {key: Path(result[key]) for key in
                     ('map_json', 'html', 'structure_svg', 'relations_svg')}
        originals = {key: path.read_bytes() for key, path in artifacts.items()}
        graph = json.loads(artifacts['map_json'].read_text())
        self.assertEqual(graph['limits'], {'nodes': 200, 'edges': 500})
        self.assertIn('<svg', originals['structure_svg'].decode())
        self.assertIn('<svg', originals['relations_svg'].decode())
        status, out, err = self.run_cli('map', self.repo, '--out', destination, '--json')
        self.assertEqual(status, 2)
        self.assertEqual(out, '')
        self.assertIn('already exists', err)
        self.assertEqual({key: path.read_bytes() for key, path in artifacts.items()}, originals)

    def test_operation_errors_do_not_look_like_successful_json(self):
        for argv in [('overview', self.base / 'missing'),
                     ('context', self.repo, 'app.py::missing'),
                     ('impact', self.repo, 'app.py::missing'),
                     ('symbols', self.repo, '--query', 'leaf', '--limit', 101),
                     ('overview', self.repo, '--languages', 'go')]:
            with self.subTest(argv=argv):
                status, out, err = self.run_cli(*argv, '--json')
                self.assertEqual(status, 2)
                self.assertEqual(out, '')
                self.assertTrue(err)

    def test_ambiguous_definition_is_excluded_and_cannot_be_used_as_evidence(self):
        (self.repo / 'ambiguous.py').write_text('def same(): return 1\ndef same(): return 2\n')
        self.assertEqual(self.data('symbols', self.repo, '--query', 'same')['matches'], [])
        self.assertEqual(self.data('overview', self.repo)['stats']['ambiguous_symbols'], 1)
        target = 'ambiguous.py::same'  # Deliberately rejected ID derived from the duplicate fixture.
        for command in ('context', 'impact'):
            status, out, err = self.run_cli(command, self.repo, target, '--json')
            self.assertEqual(status, 2)
            self.assertEqual(out, '')
            self.assertIn('Ambiguous symbol', err)

    def test_parse_error_is_explicit_without_discarding_other_valid_files(self):
        (self.repo / 'broken.py').write_text('def broken(:\n')
        result = self.data('overview', self.repo)
        self.assertEqual(result['stats']['parse_errors'], 1)
        self.assertEqual(result['parse_errors'][0]['file'], 'broken.py')
        self.assertEqual(result['stats']['symbols'], 2)


HAS_JS = all(importlib.util.find_spec(name) is not None for name in
             ('tree_sitter', 'tree_sitter_javascript', 'tree_sitter_typescript'))


@unittest.skipUnless(HAS_JS, 'requires optional js extra; base installation rejection is checked separately')
class JSContractTests(CLIHarness, unittest.TestCase):
    def setUp(self):
        super().setUp()
        (self.repo / 'core.ts').write_text('export function add(value: number) { return value + 1; }\n')
        (self.repo / 'consumer.ts').write_text(
            "import { add } from './core.ts';\nexport function call(value: number) { return add(value); }\n")

    def test_js_selection_and_context_impact_use_explicit_source_evidence(self):
        languages = ('--languages', 'typescript')
        matches = self.data('symbols', self.repo, '--query', 'add', *languages)['matches']
        self.assertEqual(len(matches), 1)
        target = matches[0]['id']
        context = self.data('context', self.repo, target, *languages)
        self.assertEqual(context['analysis']['requested_languages'], ['typescript'])
        self.assertEqual(context['analysis']['source_extensions'], {'typescript': ['.ts', '.tsx']})
        self.assertFalse(context['analysis']['esm_source_resolution']['runtime_resolution'])
        impact = self.data('impact', self.repo, target, *languages)
        self.assertEqual(impact['status'], 'bounded')
        self.assertEqual(impact['affected_symbols'][0]['symbol'], 'consumer.ts::call')
        edge = impact['affected_symbols'][0]['call_path_evidence'][0]
        self.assertEqual(edge['line'], 2)
        self.assertEqual(edge['via_esm_import']['specifier'], './core.ts')

    def test_js_snapshot_rejection_does_not_write_output(self):
        snapshot = self.base / 'snapshot.json'
        status, out, err = self.run_cli('context', self.repo, 'core.ts::add', '--languages',
                                      'typescript', '--snapshot-out', snapshot, '--json')
        self.assertEqual(status, 2)
        self.assertEqual(out, '')
        self.assertIn('--json', err)
        self.assertFalse(snapshot.exists())
