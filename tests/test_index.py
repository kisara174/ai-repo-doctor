"""Selected language fingerprints and isolation of Python module semantics."""

from pathlib import Path
import shutil
import tempfile
import unittest

from repo_doctor.case import source_fingerprint
from repo_doctor.index import build_index
from tests.test_js_ts import FIXTURES, HAS_EXTRA


@unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
class MixedIndexTests(unittest.TestCase):
    def test_selected_language_fingerprint_and_python_calls_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'repo'
            shutil.copytree(FIXTURES, root)
            (root / 'core.py').write_text('def inc():\n    return 42\n')
            (root / 'app.py').write_text('from core import inc\ndef entry():\n    return inc()\n')
            idx = build_index(root, languages=('python', 'javascript', 'typescript'))
            self.assertTrue({'app.py::entry', 'core.js::add', 'core.ts::inc'} <= set(idx.symbols))
            self.assertEqual([(e.caller, e.callee, e.line) for e in idx.call_edges],
                             [('app.py::entry', 'core.py::inc', 3)])
            self.assertIn('duplicate.ts::same', idx.ambiguous_symbols)
            self.assertNotIn('duplicate.ts::same', idx.symbols)
            before = source_fingerprint(idx)
            python_before = source_fingerprint(build_index(root))
            (root / 'core.ts').write_text('export function inc(n: number) { return n + 2; }\n')
            self.assertNotEqual(source_fingerprint(build_index(root, languages=('python', 'javascript', 'typescript'))), before)
            self.assertEqual(source_fingerprint(build_index(root)), python_before)
