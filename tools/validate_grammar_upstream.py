"""Run unchanged upstream corpus expectations with the frozen patched parsers."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'backends/jsx-grammars'
    data = json.loads((root / 'provenance.json').read_text())
    args.out.mkdir(parents=True, exist_ok=False)
    cli = args.cli.resolve()
    with tempfile.TemporaryDirectory(prefix='repo-doctor-upstream-') as directory:
        temp = Path(directory)
        for name, source in data['upstream'].items():
            work = temp / name
            subprocess.run(['git', 'init', '-q', str(work)], check=True)
            subprocess.run(['git', '-C', str(work), 'fetch', '-q', '--depth', '1', source['url'], source['commit']], check=True)
            subprocess.run(['git', '-C', str(work), 'checkout', '-q', '--detach', 'FETCH_HEAD'], check=True)
            actual = subprocess.check_output(['git', '-C', str(work), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != source['commit']:
                raise ValueError('Unexpected upstream commit')
        for name, files in (('javascript', ('grammar.js', 'src')),
                            ('javascript-tsx-base', ('grammar.js',)), ('typescript', ('tsx/src',))):
            for relative in files:
                source, dest = root / 'vendor' / name / relative, temp / name / relative
                if source.is_dir():
                    shutil.copytree(source, dest, dirs_exist_ok=True)
                else:
                    shutil.copyfile(source, dest)
        link = temp / 'typescript/node_modules/tree-sitter-javascript'
        link.parent.mkdir()
        link.symlink_to(temp / 'javascript-tsx-base', target_is_directory=True)
        results = []
        for name in ('javascript', 'typescript'):
            result = subprocess.run([str(cli), 'test', '--overview-only'], cwd=temp / name,
                                    capture_output=True, text=True)
            (args.out / (name + '.txt')).write_text(result.stdout + result.stderr)
            results.append({'project': name, 'exit_code': result.returncode})
        (args.out / 'summary.json').write_text(json.dumps({'upstream': data['upstream'], 'results': results}, indent=2))
        if any(r['exit_code'] for r in results):
            parser.exit(1, 'Upstream corpus failed; original expectations were not updated\n')


if __name__ == '__main__':
    main()
