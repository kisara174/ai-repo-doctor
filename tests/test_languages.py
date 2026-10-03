"""Language selection and source decoding contracts, independent of native extras."""

from pathlib import Path
import tempfile
import unittest

from repo_doctor.source import read_source


class LanguageTests(unittest.TestCase):
    def test_csv_selection_rejects_empty_unknown_and_normalizes_order(self):
        from repo_doctor.languages import normalize_languages
        self.assertEqual(normalize_languages('typescript,python,javascript,python'),
                         ('python', 'javascript', 'typescript'))
        for value in ('', 'python,', 'go', 'auto', 'python,,typescript'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_languages(value)

    def test_only_implementation_extensions_are_analyzed(self):
        from repo_doctor.languages import language_for_path
        for path, expected in [('a.py', 'python'), ('a.js', 'javascript'),
                               ('a.mjs', 'javascript'), ('a.ts', 'typescript'),
                               ('a.d.ts', None), ('a.tsx', None), ('a.cjs', None),
                               ('a.mts', None), ('a.cts', None), ('a.jsx', None)]:
            with self.subTest(path=path):
                self.assertEqual(language_for_path(path), expected)

    def test_error_and_limit_metadata_is_sorted_bounded_and_counts_omissions(self):
        from repo_doctor.languages import analysis_metadata
        from repo_doctor.model import RepoIndex, AnalysisLimit, ParseError
        index = RepoIndex(Path('/tmp'), 'walk', (0, 0), analysis_languages=('typescript',))
        index.analysis_limits = [AnalysisLimit(f'z{i:02d}.ts', 1, 'unresolved', 'Unknown') for i in range(60)]
        index.parse_errors = [ParseError('a.ts', 2, 'Invalid syntax')]
        meta = analysis_metadata(index)
        self.assertEqual(len(meta['limits']), 50)
        self.assertEqual(meta['limits_omitted'], 11)
        self.assertEqual(meta['limits'][0], {'file': 'a.ts', 'line': 2, 'reason': 'parse-error', 'message': 'Invalid syntax'})

    def test_js_decoding_ignores_python_cookie_and_keeps_bom_crlf_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'a.js').write_bytes('// coding: latin-1\r\nconst 名 = "中文😀";\r\n'.encode('utf-8-sig'))
            self.assertEqual(read_source(root, 'a.js', language='javascript'),
                             '// coding: latin-1\r\nconst 名 = "中文😀";\r\n')
            (root / 'a.ts').write_bytes(b'// coding: latin-1\nconst a="\xff";')
            with self.assertRaises(UnicodeError):
                read_source(root, 'a.ts', language='typescript')
            (root / 'a.py').write_bytes(b'# coding: latin-1\nvalue="\xe9"\n')
            self.assertIn('é', read_source(root, 'a.py'))

    def test_new_language_uses_existing_path_and_root_identity_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'a.js').write_text('function a() {}')
            (root / 'link.js').symlink_to(root / 'a.js')
            for path, identity in [('link.js', None), ('../a.js', None),
                                   ('a.js', (0, 0))]:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    read_source(root, path, identity, language='javascript')
