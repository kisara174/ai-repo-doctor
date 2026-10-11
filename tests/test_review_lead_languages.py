"""Coverage leads describe the actual source language, not presumed defects."""
import tempfile
import unittest
from pathlib import Path

from repo_doctor.agent_tools import build_overview
from repo_doctor.case import _static_issues
from repo_doctor.index import build_index
from tests.test_js_ts import HAS_EXTRA


class ReviewLeadLanguageTests(unittest.TestCase):
    def make_index(self, path, source, language):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / path).write_text(source)
        return build_index(root, languages=(language,))

    def test_python_lead_preserves_identity_and_review_state(self):
        idx = self.make_index('app.py', 'def broken(:\n', 'python')
        issue = _static_issues(idx)[0]
        self.assertIn('Python', issue['title'])
        self.assertEqual(issue['id'], 'S-001')
        self.assertEqual(issue['human_status'], 'unreviewed')
        self.assertEqual(issue['category'], 'parse_error')
        self.assertEqual(issue['evidence'][0]['file'], 'app.py')

    @unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
    def test_javascript_and_typescript_leads_use_actual_backend(self):
        for path, language, display in [('app.js', 'javascript', 'JavaScript'),
                                        ('app.ts', 'typescript', 'TypeScript')]:
            with self.subTest(language=language):
                idx = self.make_index(path, 'export function broken( {\n', language)
                issue = _static_issues(idx)[0]
                self.assertIn(display, issue['title'])
                self.assertIn('Tree-sitter', issue['reasoning'])
                self.assertNotIn('Python', issue['reasoning'])
                self.assertEqual(issue['id'], 'S-001')
                self.assertEqual(issue['human_status'], 'unreviewed')
                self.assertIn(display, build_overview(idx)['review_leads'][0]['subject'])
