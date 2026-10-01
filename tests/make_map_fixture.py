"""Controlled input for the optional DOM integration check."""

import sys
from pathlib import Path


root = Path(sys.argv[1])
root.mkdir(parents=True)
(root / 'a.py').write_text('def target():\n    return 1\n\nclass Box:\n    def go(self):\n        return target()\n', encoding='utf-8')
(root / 'b.py').write_text('from a import target\n\ndef run():\n    return target()\n', encoding='utf-8')
(root / 'test_a.py').write_text('from a import target\ndef test_it(): return target()\n', encoding='utf-8')
