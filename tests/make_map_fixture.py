"""Controlled input for the optional DOM integration check."""

import sys
from pathlib import Path


root = Path(sys.argv[1])
root.mkdir(parents=True)
(root / 'a.py').write_text('def target():\n    return 1\n\nclass Box:\n    def go(self):\n        return target()\n', encoding='utf-8')
(root / 'b.py').write_text('from a import target\n\ndef run():\n    return target()\n', encoding='utf-8')
(root / 'test_a.py').write_text('from a import target\ndef test_it(): return target()\n', encoding='utf-8')
for directory in ('pkg/deep', 'other'):
    folder = root / directory
    folder.mkdir(parents=True)
    (folder / 'README.md').write_text('Structure navigation fixture.\n', encoding='utf-8')
if '--mixed' in sys.argv[2:]:
    folder = root / 'web'
    folder.mkdir()
    (folder / 'core.js').write_text('export function target() { return 1; }\n', encoding='utf-8')
    (folder / 'app.js').write_text("import {target} from './core.js';\nexport function run() { return target(); }\n", encoding='utf-8')
    (folder / 'core.ts').write_text('export function target(value: number) { return value; }\n', encoding='utf-8')
