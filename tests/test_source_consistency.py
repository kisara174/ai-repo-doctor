"""Source mutations must never produce successful evidence from stale indexes."""
import contextlib
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_doctor import cli, index as index_module
from repo_doctor.agent_tools import build_overview
from repo_doctor.case import source_fingerprint
from repo_doctor.context import build_context, build_impact
from repo_doctor.index import build_index
from repo_doctor.repo_map import write_map
from repo_doctor.symbols import search_symbols
from tests.test_js_ts import HAS_EXTRA


class SourceConsistencyTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / 'app.py'
        self.original = b'def original():\n    return 1\n'
        self.path.write_bytes(self.original)

    def test_single_cli_context_edit_after_parse_rejects_snapshot(self):
        parse = index_module.parse_python_file
        def edited(*args, **kwargs):
            result = parse(*args, **kwargs)
            self.path.write_text('def replacement():\n    return 2\n')
            return result
        snapshot = self.root / 'snapshot.json'
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(index_module, 'parse_python_file', side_effect=edited), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = cli.main(['context', str(self.root), 'app.py::original',
                               '--snapshot-out', str(snapshot), '--json'])
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), '')
        self.assertIn('source changed', stderr.getvalue().lower())
        self.assertFalse(snapshot.exists())

    def test_all_core_outputs_reject_modified_source(self):
        operations = {
            'overview': lambda idx: build_overview(idx),
            'symbols': lambda idx: search_symbols(idx, 'original'),
            'context': lambda idx: build_context(idx, 'app.py::original'),
            'impact': lambda idx: build_impact(idx, 'app.py::original'),
            'map': lambda idx: write_map(idx, self.root / 'map-output'),
        }
        for name, operation in operations.items():
            with self.subTest(command=name):
                self.path.write_bytes(self.original)
                idx = build_index(self.root)
                self.path.write_text('def replacement():\n    return 2\n')
                with self.assertRaisesRegex(ValueError, 'source changed'):
                    operation(idx)
                self.assertFalse((self.root / 'map-output').exists())

    def test_selected_source_addition_rejects_old_index(self):
        idx = build_index(self.root)
        (self.root / 'added.py').write_text('def added():\n    return 3\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            build_overview(idx)

    def test_deletion_or_bad_encoding_is_not_swallowed_by_fingerprint(self):
        for mutation in ('delete', 'invalid-encoding'):
            with self.subTest(mutation=mutation):
                self.path.write_bytes(self.original)
                idx = build_index(self.root)
                if mutation == 'delete':
                    self.path.unlink()
                else:
                    self.path.write_bytes(b'\xff')
                with self.assertRaisesRegex(ValueError, 'source changed'):
                    source_fingerprint(idx)

    def test_stable_invalid_encoding_remains_a_coverage_error(self):
        self.path.write_bytes(b'\xff')
        idx = build_index(self.root)
        overview = build_overview(idx)
        self.assertEqual(overview['stats']['parse_errors'], 1)
        expected = hashlib.sha256(b'app.py\0<unreadable>\0').hexdigest()
        self.assertEqual(overview['source_fingerprint'], expected)

    def test_stable_source_keeps_fingerprint_and_physical_lines(self):
        self.path.write_bytes(b'\xef\xbb\xbfdef original():\r\n    return 1\r\n')
        idx = build_index(self.root)
        # Existing fingerprint hashes decoded text, preserving CRLF.
        expected = hashlib.sha256(b'app.py\0def original():\r\n    return 1\r\n\0').hexdigest()
        self.assertEqual(source_fingerprint(idx), expected)
        self.assertEqual(build_context(idx, 'app.py::original')['blocks'][0]['lines'][0]['text'],
                         'def original():')

    def test_related_caller_change_invalidates_target_context(self):
        (self.root / 'caller.py').write_text('from app import original\ndef caller():\n    return original()\n')
        idx = build_index(self.root)
        (self.root / 'caller.py').write_text('def caller():\n    return None\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            build_context(idx, 'app.py::original')

    def test_python_digest_is_the_actual_input_even_after_parser_hook_edit(self):
        parse = index_module.parse_python_file
        def edited(*args, **kwargs):
            result = parse(*args, **kwargs)
            self.path.write_text('def replacement():\n    return 2\n')
            return result
        with patch.object(index_module, 'parse_python_file', side_effect=edited):
            idx = build_index(self.root)
        self.assertEqual(idx.source_digests['app.py'], hashlib.sha256(self.original).hexdigest())
        with self.assertRaisesRegex(ValueError, 'source changed'):
            build_overview(idx)

    @unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
    def test_js_actual_input_identity_and_stable_bad_encoding(self):
        js = self.root / 'app.js'
        raw = b'export function original() { return 1; }\n'
        js.write_bytes(raw)
        idx = build_index(self.root, languages=('javascript',))
        self.assertEqual(idx.source_digests['app.js'], hashlib.sha256(raw).hexdigest())
        js.write_bytes(b'\xff')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            build_overview(idx)
        stable = build_index(self.root, languages=('javascript',))
        self.assertEqual(build_overview(stable)['stats']['parse_errors'], 1)

    @unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
    def test_js_new_ambiguity_candidate_invalidates_old_relationships(self):
        (self.root / 'core.ts').write_text('export function inc() { return 1; }\n')
        (self.root / 'consumer.ts').write_text("import {inc} from './core';\nexport function run() { return inc(); }\n")
        idx = build_index(self.root, languages=('typescript',))
        self.assertTrue(idx.call_edges)
        (self.root / 'core.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            build_impact(idx, 'core.ts::inc')
