"""Reproduce frozen grammar outputs in a temporary workspace; never runs target code."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ('parser.c', 'grammar.json', 'node-types.json',
           'tree_sitter/alloc.h', 'tree_sitter/array.h', 'tree_sitter/parser.h')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', type=Path, default=ROOT / 'tools/node_modules/.bin/tree-sitter')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true', help='Explicitly update generated outputs and their checksums')
    args = parser.parse_args()
    data = json.loads((ROOT / 'provenance.json').read_text())
    cli = args.cli.resolve()
    actual_cli = subprocess.check_output([str(cli), '--version'], text=True).split()[1]
    actual_node = subprocess.check_output(['node', '--version'], text=True).strip().removeprefix('v')
    if (actual_cli, actual_node) != (data['generator']['tree_sitter_cli'], data['generator']['node']):
        parser.exit(1, 'Generator/Node version does not match provenance\n')
    with tempfile.TemporaryDirectory(prefix='repo-doctor-grammar-') as directory:
        temp = Path(directory)
        shutil.copytree(ROOT / 'vendor', temp / 'vendor')
        link = temp / 'vendor/typescript/node_modules/tree-sitter-javascript'
        link.parent.mkdir()
        link.symlink_to(temp / 'vendor/javascript-tsx-base', target_is_directory=True)
        differences = []
        for name, abi in (('javascript', 15), ('typescript/tsx', 14)):
            work = temp / 'vendor' / name
            subprocess.run([str(cli), 'generate', '--abi', str(abi)], cwd=work, check=True)
            for file in OUTPUTS:
                relative = 'vendor/' + name + '/src/' + file
                generated = (temp / relative).read_bytes()
                committed = ROOT / relative
                if generated != committed.read_bytes():
                    differences.append(relative)
                    if args.write:
                        committed.write_bytes(generated)
                        data['files'][relative] = hashlib.sha256(generated).hexdigest()
        if args.write:
            (ROOT / 'provenance.json').write_text(json.dumps(data, indent=2) + '\n')
        elif differences:
            parser.exit(1, 'Generated grammar differs: ' + ', '.join(differences) + '\n')
        print(json.dumps({'status': 'written' if args.write else 'passed',
                          'generated_files': len(OUTPUTS) * 2, 'differences': differences}))


if __name__ == '__main__':
    main()
