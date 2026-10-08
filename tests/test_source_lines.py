"""Regressions for parser coordinates versus evidence text; expected lines are literal."""
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from repo_doctor.cli import main, _verify_selected_source
from repo_doctor.context import build_context
from repo_doctor.evidence import validate_findings
from repo_doctor.index import build_index
from tests.test_js_ts import HAS_EXTRA


class PythonSourceLineTests(unittest.TestCase):
    def make_index(self, raw):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve()
        (root / 'app.py').write_bytes(raw)
        return build_index(root)

    def finding(self, line, quote):
        return {'title': 'Investigation', 'category': 'reliability', 'confidence': 0.5,
                'reasoning': 'Inspect this source.', 'impact': 'Unknown until reviewed.',
                'suggested_fix': 'Review the source.',
                'evidence': [{'file': 'app.py', 'start_line': line, 'end_line': line,
                              'quote': quote, 'symbol': 'app.py::target'}]}

    def test_context_keeps_non_newline_separators_at_their_physical_line(self):
        for separator in ('\f', '\v', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029'):
            with self.subTest(separator=repr(separator)):
                index = self.make_index(('# marker' + separator + '\ndef target():\n    return 1\n').encode())
                context = build_context(index, 'app.py::target')
                self.assertEqual(context['blocks'][0]['lines'],
                                 [{'line': 2, 'text': 'def target():'},
                                  {'line': 3, 'text': '    return 1'}])
                self.assertEqual(index.files[0].lines, 3)
                bounded = build_context(index, 'app.py::target', max_lines=1)
                self.assertEqual(bounded['blocks'][0]['lines'], [{'line': 2, 'text': 'def target():'}])
                self.assertTrue(bounded['budget_exhausted'])

    def test_python_newline_encodings_keep_ast_coordinates(self):
        for ending in ('\n', '\r\n', '\r'):
            with self.subTest(ending=repr(ending)):
                index = self.make_index(ending.join(['# marker\f', 'def target():', '    return 1', '']).encode())
                self.assertEqual(index.symbols['app.py::target'].start_line, 2)
                self.assertEqual(build_context(index, 'app.py::target')['blocks'][0]['lines'],
                                 [{'line': 2, 'text': 'def target():'}, {'line': 3, 'text': '    return 1'}])

    def test_control_characters_inside_string_literal_preserve_source_quote(self):
        line = '    return "a\f\u2028b"'
        index = self.make_index(('def target():\n' + line + '\n').encode())
        self.assertEqual(build_context(index, 'app.py::target')['blocks'][0]['lines'][1],
                         {'line': 2, 'text': line})

    def test_findings_accept_correct_physical_quote_after_formfeed(self):
        index = self.make_index(b'# marker\f\ndef target():\n    return 1\n')
        result = validate_findings(index, self.finding(3, 'return 1'))
        self.assertEqual(len(result['accepted']), 1)
        self.assertEqual(result['rejected'], [])

    def test_findings_reject_quote_shifted_to_another_physical_line(self):
        index = self.make_index(b'# marker\f\ndef target():\n    return 1\n')
        result = validate_findings(index, self.finding(3, 'def target():'))
        self.assertEqual(result['accepted'], [])
        self.assertIn('quote', ' '.join(result['rejected'][0]['reasons']))

    def test_selected_source_verifier_accepts_physical_lines(self):
        index = self.make_index(b'# marker\f\ndef target():\n    return 1\n')
        try:
            _verify_selected_source(index, {'blocks': [{'file': 'app.py', 'lines':
                [{'line': 2, 'text': 'def target():'}, {'line': 3, 'text': '    return 1'}]}]})
        except ValueError as exc:
            self.fail(str(exc))

    def test_encoded_source_and_trailing_blank_lines_keep_quote_coordinates(self):
        for prefix, encoding in (('# coding: latin-1\n', 'latin-1'), ('\ufeff', 'utf-8')):
            for ending, count in (('', 3), ('\n', 3), ('\n\n', 4)):
                with self.subTest(encoding=encoding, ending=repr(ending)):
                    # Both inputs have the declaration on physical line 2.
                    comment = '# marker\f\n' if encoding == 'utf-8' else ''
                    source = prefix + comment + "def target():\n    return 'café'" + ending
                    index = self.make_index(source.encode(encoding))
                    self.assertEqual(index.files[0].lines, count)
                    self.assertEqual(build_context(index, 'app.py::target')['blocks'][0]['lines'],
                                     [{'line': 2, 'text': 'def target():'},
                                      {'line': 3, 'text': "    return 'café'"}])

    def test_snapshot_import_uses_true_physical_line_and_rejects_shifted_quote(self):
        index = self.make_index(b'# marker\f\ndef target():\n    return 1\n')
        root = index.root
        case, snapshot, findings = root.parent / (root.name + '-case'), root / 'context.json', root / 'findings.json'
        self.addCleanup(shutil.rmtree, case, True)
        def command(*args, expected=0):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                status = main([str(x) for x in args])
            self.assertEqual(status, expected, err.getvalue())
            return json.loads(out.getvalue())
        command('report', 'create', root, '--out', case, '--json')
        context = command('context', root, 'app.py::target', '--snapshot-out', snapshot, '--json')
        self.assertEqual(context['blocks'][0]['lines'][1], {'line': 3, 'text': '    return 1'})
        findings.write_text(json.dumps({'findings': [self.finding(3, 'return 1'), self.finding(3, 'def target():')]}))
        result = command('findings', 'import', case, '--from', findings, '--context', snapshot, '--producer', 'codex', '--json', expected=1)
        self.assertEqual(result['accepted_issue_ids'], ['A-001'])
        self.assertEqual(len(result['rejected']), 1)


@unittest.skipUnless(HAS_EXTRA, 'requires optional js extra')
class FrontendSourceLineTests(unittest.TestCase):
    def test_js_ts_line_evidence_matches_lf_backend_coordinates(self):
        for extension, language in (('.js', 'javascript'), ('.ts', 'typescript'), ('.tsx', 'typescript')):
            for marker in ('\f', '\v', '\u2028', '\u2029', '\r'):
                with self.subTest(extension=extension, marker=repr(marker)), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp).resolve()
                    source = '/* marker' + marker + '*/\nexport function target() { return 1; }\n'
                    (root / ('app' + extension)).write_bytes(source.encode())
                    index = build_index(root, languages=(language,))
                    sid = 'app' + extension + '::target'
                    self.assertEqual(index.parse_errors, [])
                    self.assertEqual(index.symbols[sid].start_line, 2)
                    self.assertEqual(build_context(index, sid)['blocks'][0]['lines'],
                                     [{'line': 2, 'text': 'export function target() { return 1; }'}])
                    self.assertEqual(index.files[0].lines, 2)
