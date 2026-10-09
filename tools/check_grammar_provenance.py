"""Check the frozen native grammar sources without loading or generating code."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def check(root: Path) -> dict:
    data = json.loads((root / 'provenance.json').read_text(encoding='utf-8'))
    if data['schema_version'] != 1 or data['language_abi'] != {'javascript': 15, 'tsx': 14}:
        raise ValueError('Unsupported grammar provenance or language ABI')
    expected = data['files']
    actual = {p.relative_to(root).as_posix()
              for folder in ('vendor', 'patches', 'licenses')
              for p in (root / folder).rglob('*') if p.is_file()}
    if actual != set(expected):
        raise ValueError('Frozen file set differs from provenance')
    for name, digest in expected.items():
        parts = PurePosixPath(name).parts
        if PurePosixPath(name).is_absolute() or '..' in parts:
            raise ValueError('Provenance file must be inside the source package')
        path = root / name
        if any((root.joinpath(*parts[:i])).is_symlink() for i in range(1, len(parts) + 1)):
            raise ValueError('Frozen sources must not be symlinks')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen source checksum mismatch: ' + name)
    for name, abi in (('javascript/src/parser.c', 15), ('typescript/tsx/src/parser.c', 14)):
        text = (root / 'vendor' / name).read_text(encoding='utf-8')
        if f'#define LANGUAGE_VERSION {abi}\n' not in text:
            raise ValueError('Generated language ABI mismatch: ' + name)
    return {'status': 'passed', 'files': len(expected), 'package_version': data['package_version']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.root.resolve())))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Grammar provenance failed: {exc}\n')


if __name__ == '__main__':
    main()
