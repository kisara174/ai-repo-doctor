import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from repo_doctor.cli import main


class AgentToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        (self.repo / 'a.py').write_text('def target():\n    return 1\n\ndef hidden():\n    return 2\n')
        (self.repo / 'b.py').write_text('from a import target\n\ndef run():\n    return target()\n')
        self.case = self.base / 'case'
        self.snapshot = self.base / 'context.json'

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                status = main(list(map(str, args)))
            except SystemExit as exc:
                status = exc.code
        return status, out.getvalue(), err.getvalue()

    def prepare(self):
        status, _, err = self.run_cli('report', 'create', self.repo, '--out', self.case, '--json')
        self.assertEqual(status, 0, err)
        status, out, err = self.run_cli('context', self.repo, 'a.py::target', '--max-lines', 2,
                                      '--snapshot-out', self.snapshot, '--json')
        self.assertEqual(status, 0, err)
        return json.loads(out)

    def finding(self, *, line=2, quote='return 1'):
        return dict(title='Investigate return', category='behavior', confidence=0.6,
                    reasoning='Candidate only.', impact='Check caller expectations.',
                    suggested_fix='Review with Codex.',
                    evidence=[dict(file='a.py', start_line=line, end_line=line, quote=quote)])

    def import_findings(self, findings):
        source = self.base / 'findings.json'
        source.write_text(json.dumps({'findings': findings}))
        return self.run_cli('findings', 'import', self.case, '--from', source,
                            '--context', self.snapshot, '--producer', 'codex', '--json')

    def test_overview_is_bounded_and_offers_target_commands(self):
        (self.repo / 'many.py').write_text('\n'.join(f'def f{i}(): return {i}' for i in range(100)))
        status, out, err = self.run_cli('overview', self.repo, '--json')
        self.assertEqual(status, 0, err)
        data = json.loads(out)
        self.assertEqual(data['stats']['python_files'], 3)
        self.assertEqual(data['stats']['symbols'], 103)
        self.assertLessEqual(len(data['sample_symbols']), 10)
        self.assertEqual(data['symbols_omitted'], 93)
        self.assertIn('context', data['next_commands'])
        self.assertNotIn('calls', data)

    def test_overview_prioritizes_a_real_parse_failure(self):
        (self.repo / 'broken.py').write_text('def broken(:\n')
        status, out, err = self.run_cli('overview', self.repo, '--json')
        self.assertEqual(status, 0, err)
        data = json.loads(out)
        self.assertTrue(data['review_leads'], 'A parse failure must be an investigation entry')
        self.assertEqual(data['review_leads'][0]['kind'], 'parse_error')
        self.assertEqual(data['review_leads'][0]['evidence'][0]['file'], 'broken.py')

    def test_snapshot_import_saves_codex_provenance_without_cloud_request(self):
        data = self.prepare()
        self.assertEqual(data['symbol'], 'a.py::target')
        status, out, err = self.import_findings([self.finding()])
        self.assertEqual(status, 0, err)
        result = json.loads(out)
        self.assertEqual(result['accepted_issue_ids'], ['A-001'])
        case = json.loads((self.case / 'case.json').read_text())
        issue = case['issues'][0]
        self.assertEqual(issue['producer'], 'codex')
        self.assertEqual(issue['evidence_status'], 'quote_verified')
        self.assertEqual(issue['human_status'], 'unreviewed')
        self.assertEqual(case['diagnoses'], [])
        self.assertNotIn('request_sha256', case['imports'][0])
        status, report, err = self.run_cli('report', 'show', self.case)
        self.assertEqual(status, 0, err)
        self.assertIn('codex', report)
        self.assertIn('A-001', report)

    def test_import_rejects_quote_outside_snapshot_and_saves_rejection(self):
        self.prepare()
        status, out, err = self.import_findings([self.finding(line=5, quote='return 2')])
        self.assertEqual(status, 1, err)
        data = json.loads(out)
        self.assertEqual(data['accepted_issue_ids'], [])
        self.assertTrue(data['rejected'])
        self.assertEqual(json.loads((self.case / 'case.json').read_text())['issues'], [])

    def test_changed_source_rejects_snapshot_without_modifying_case(self):
        self.prepare()
        before = (self.case / 'case.json').read_bytes()
        (self.repo / 'a.py').write_text('def target():\n    return 3\n')
        status, _, err = self.import_findings([self.finding()])
        self.assertEqual(status, 2)
        self.assertIn('source changed', err.lower())
        self.assertEqual((self.case / 'case.json').read_bytes(), before)

    def test_altered_snapshot_is_rejected_without_modifying_case(self):
        self.prepare()
        data = json.loads(self.snapshot.read_text())
        data['context']['blocks'][0]['lines'][1]['text'] = '    return 999'
        self.snapshot.write_text(json.dumps(data))
        status, _, err = self.import_findings([self.finding()])
        self.assertEqual(status, 2)
        self.assertIn('snapshot', err.lower())
        self.assertEqual(json.loads((self.case / 'case.json').read_text())['issues'], [])

    def test_snapshot_cannot_replace_repository_source(self):
        original = (self.repo / 'a.py').read_bytes()
        status, _, _ = self.run_cli('context', self.repo, 'a.py::target',
                                    '--snapshot-out', self.repo / 'a.py', '--json')
        self.assertEqual(status, 2)
        self.assertEqual((self.repo / 'a.py').read_bytes(), original)

    def test_snapshot_rejects_a_budget_that_cannot_be_imported(self):
        status, _, err = self.run_cli('context', self.repo, 'a.py::target', '--max-lines', 121,
                                      '--snapshot-out', self.snapshot, '--json')
        self.assertEqual(status, 2, err)
        self.assertFalse(self.snapshot.exists())

    def test_codex_review_is_recorded_without_claiming_human_confirmation(self):
        self.prepare()
        status, _, err = self.import_findings([self.finding()])
        self.assertEqual(status, 0, err)
        status, out, err = self.run_cli('issue', self.case, 'A-001', '--status', 'confirmed',
                                      '--note', 'Codex inspected caller behavior', '--actor', 'codex', '--json')
        self.assertEqual(status, 0, err)
        issue = json.loads(out)
        self.assertEqual(issue['human_history'][-1]['actor'], 'codex')
        status, report, err = self.run_cli('report', 'show', self.case)
        self.assertEqual(status, 0, err)
        self.assertIn('codex', report)
        self.assertNotIn('人工判断：confirmed', report)

    def test_skill_export_produces_portable_instructions_and_preserves_existing_files(self):
        destination = self.base / 'repo-doctor'
        status, out, err = self.run_cli('skill', 'export', '--out', destination)
        self.assertEqual(status, 0, err)
        self.assertTrue((destination / 'SKILL.md').is_file())
        original = (destination / 'SKILL.md').read_bytes()
        status, _, err = self.run_cli('skill', 'export', '--out', destination)
        self.assertEqual(status, 2)
        self.assertEqual((destination / 'SKILL.md').read_bytes(), original)


class JSSnapshotTests(unittest.TestCase):
    def test_native_api_rejects_js_snapshot_before_source_collection(self):
        from repo_doctor.agent_tools import build_snapshot
        from repo_doctor.index import build_index
        from repo_doctor.context import build_context
        from tests.test_js_ts import HAS_EXTRA, FIXTURES
        if not HAS_EXTRA:
            self.skipTest('requires optional js extra')
        index = build_index(FIXTURES, languages=('typescript',))
        context = build_context(index, 'core.ts::inc')
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            build_snapshot(index, context, ())


if __name__ == '__main__':
    unittest.main()
