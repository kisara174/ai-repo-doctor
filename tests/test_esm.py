"""Finite ESM file resolution never guesses ambiguous or excluded sources."""

from pathlib import Path
import tempfile
import unittest

from repo_doctor.index import build_index
from tests.test_js_ts import HAS_EXTRA


@unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
class ESMTests(unittest.TestCase):
    def test_ts_js_substitution_unique_but_not_ambiguous_or_unselected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'core.ts').write_text('export function inc(v: number) { return v+1; }')
            (root / 'app.ts').write_text("import {inc} from './core.js';\nexport {inc as step} from './core.js';")
            index = build_index(root, languages=('typescript',))
            self.assertEqual([(e.source, e.target, e.line) for e in index.import_edges],
                             [('app.ts', 'core.ts', 1), ('app.ts', 'core.ts', 2)])
            self.assertEqual(index.esm_imports[0].resolved_file, 'core.ts')
            for name in ('core.js', 'core.d.ts', 'core.tsx'):
                (root / name).write_text('')
                self.assertEqual(build_index(root, languages=('typescript',)).import_edges, [])
                (root / name).unlink()

    def test_external_dynamic_extensionless_invalid_and_type_only_do_not_become_runtime_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'core.ts').write_text('export function inc(v: number) { return v+1; }')
            (root / 'app.ts').write_text("import type {inc} from './core.js';\nimport {inc as a} from 'pkg';\nimport {inc as b} from './core';\nexport function run() { import('./core.js'); return a(1); }")
            index = build_index(root, languages=('typescript',))
            self.assertTrue(index.esm_imports[0].type_only)
            self.assertEqual(index.call_edges, [])
            self.assertNotIn(('app.ts', 'core.ts', 3), [(e.source, e.target, e.line) for e in index.import_edges])
            self.assertTrue(any(l.reason == 'external-or-alias' for l in index.analysis_limits))
            self.assertTrue(any(l.reason == 'calls-not-supported' for l in index.analysis_limits))
