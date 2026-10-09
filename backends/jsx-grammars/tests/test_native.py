"""Run against an installed companion, not a source or ctypes replacement."""
import json
from importlib.metadata import version
from pathlib import Path
import unittest

import ai_repo_doctor_grammars as grammar
from tree_sitter import Language, Parser


class NativeGrammarTests(unittest.TestCase):
    def test_installed_identity_language_abi_and_provenance(self):
        self.assertEqual(version('ai-repo-doctor-grammars'), '0.1.0')
        self.assertIn('site-packages', Path(grammar.__file__).parts)
        data = json.loads(Path(grammar.__file__).with_name('provenance.json').read_text())
        self.assertEqual(data['package_version'], '0.1.0')
        for fn, abi in ((grammar.language_javascript, 15), (grammar.language_tsx, 14)):
            self.assertEqual(Language(fn()).abi_version, abi)

    def test_quoted_attributes_preserve_raw_source_and_entities(self):
        values = ('?a=1&b=2', 'a&emoji=&slug=x', '&', 'a&b', 'a& b', 'a&1',
                  'a&amp;b', '&#38;&#x26;', 'a&unknown;', '中文😀&slug=x',
                  'x\\y&b=2', 'x<y&b=2', 'x\ny&b=2')
        for fn in (grammar.language_javascript, grammar.language_tsx):
            parser = Parser(Language(fn()))
            for quote in ('"', "'"):
                for value in values:
                    with self.subTest(grammar=fn.__name__, quote=quote, value=value):
                        raw = ('// 中文😀\r\nexport const View = () => <img src=' + quote + value + quote + ' />;\n').encode()
                        tree = parser.parse(raw)
                        self.assertFalse(tree.root_node.has_error)
                        self.assertEqual(tree.root_node.end_byte, len(raw))
                        self.assertEqual(tree.root_node.text, raw)
                        if value in ('a&amp;b', '&#38;&#x26;'):
                            pending, references = [tree.root_node], []
                            while pending:
                                node = pending.pop()
                                pending.extend(node.children)
                                if node.type == 'html_character_reference':
                                    references.append(node.text)
                            self.assertEqual(len(references), 1 if value == 'a&amp;b' else 2)

    def test_malformed_code_does_not_become_valid(self):
        for fn in (grammar.language_javascript, grammar.language_tsx):
            parser = Parser(Language(fn()))
            for tail in (b'export function broken() {\n',
                         b'export function broken() { return helper(; }\n',
                         b'export const broken = () => <img src="?x=1&b=2 />;\n'):
                raw = b'export const View = () => <img src="?a=1&b=2" />;\n' + tail
                self.assertTrue(parser.parse(raw).root_node.has_error)


if __name__ == '__main__':
    unittest.main()
