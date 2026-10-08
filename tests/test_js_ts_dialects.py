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
