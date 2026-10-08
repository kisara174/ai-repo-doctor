"""Offline documentation checks catch broken instructions without fetching URLs."""

from pathlib import Path
import tempfile
import unittest

from tools.check_public_docs import PUBLIC_DOCS, check_document, check_public_docs


class PublicDocsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.doc = self.root / 'docs/start.md'
        self.doc.parent.mkdir()

    def check(self, text):
        self.doc.write_text(text)
        return check_document(self.root, self.doc, '1.0.0.dev1')

    def test_valid_relative_encoded_and_external_links(self):
        (self.doc.parent / 'target file.md').write_text('# Target')
        errors = self.check('[a](target%20file.md#section) [b](<target file.md>) '
                            '[c](https://example.invalid/not-fetched) [d](#local)')
        self.assertEqual(errors, [])

    def test_missing_relative_target_and_reference_link_are_reported(self):
        errors = self.check('[lost](missing.md)\n[other][ref]\n\n[ref]: missing-too.md\n')
        self.assertEqual(len(errors), 2)
        self.assertTrue(all('missing' in row for row in errors))

    def test_code_examples_are_not_parsed_as_links(self):
        self.assertEqual(self.check('```text\n[example](not-a-real-link.md)\n```\n'), [])

    def test_maintainer_home_in_code_block_is_rejected(self):
        errors = self.check('```sh\n/Users/example/private/bin/repo-doctor overview REPO\n```\n')
        self.assertTrue(any('maintainer' in row for row in errors))
        self.assertEqual(self.check('```sh\n"$HOME/bin/repo-doctor" overview /absolute/path/to/repo\n```'), [])

    def test_install_version_mismatch_and_explicit_public_example(self):
        install = '```sh\npip install ai_repo_doctor-0.8.0-py3-none-any.whl\n```\n'
        self.assertTrue(any('version' in row for row in self.check(install)))
        self.assertEqual(self.check('<!-- repo-doctor-install-versions: 0.8.0 -->\n' + install), [])
        self.assertTrue(any('version' in row for row in self.check('<!-- repo-doctor-install-versions: 0.8.0 -->\n' + install.replace('0.8.0', '0.9.0'))))

    def test_development_marker_must_match_source_version(self):
        self.assertTrue(any('development' in row for row in self.check('<!-- repo-doctor-development-version: 0.9.0 -->')))
        self.assertEqual(self.check('<!-- repo-doctor-development-version: 1.0.0.dev1 -->'), [])

    def test_complete_public_set_is_required_and_version_is_read_without_import(self):
        version = self.root / 'repo_doctor/_version.py'
        version.parent.mkdir()
        version.write_text('__version__ = "1.0.0.dev1"\nraise RuntimeError("never import")\n')
        for relative in PUBLIC_DOCS:
            path = self.root / relative
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_text('# Valid\n')
        self.assertEqual(check_public_docs(self.root), [])
        (self.root / PUBLIC_DOCS[-1]).unlink()
        self.assertTrue(any(PUBLIC_DOCS[-1] in row for row in check_public_docs(self.root)))
