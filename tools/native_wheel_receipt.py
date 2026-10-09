"""Record checked native wheel identities after CI build and ABI audits."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheelhouse', type=Path, required=True)
    parser.add_argument('--platform', choices=('linux', 'macos'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    wheels = list(args.wheelhouse.glob('*.whl'))
    if len(wheels) != 1:
        parser.exit(1, 'Expected exactly one native wheel for this platform\n')
    records = []
    for wheel in wheels:
        audit = args.out / (wheel.name + '.abi3.json')
        subprocess.run([sys.executable, '-m', 'abi3audit', '--strict', '--report', '--output', str(audit), str(wheel)], check=True)
        with ZipFile(wheel) as archive:
            provenance = json.loads(archive.read('ai_repo_doctor_grammars/provenance.json'))
            if provenance['package_version'] != '0.1.0':
                raise ValueError('Unexpected native version')
            if sys.platform == 'darwin':
                binary = next(n for n in archive.namelist() if n.endswith('.abi3.so'))
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / 'binding.so'
                    path.write_bytes(archive.read(binary))
                    result = subprocess.check_output(['otool', '-l', str(path)], text=True)
                    (args.out / 'macos-load-commands.txt').write_text(result)
                    minimums = re.findall(r'^\s*minos (\S+)', result, re.MULTILINE)
                    if not minimums or any(tuple(map(int, v.split('.')))[:2] > (11, 0) for v in minimums):
                        raise ValueError('Native binary does not honor macOS 11.0 deployment target')
        records.append({'file': wheel.name, 'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
                        'provenance': provenance})
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    (args.out / 'receipt.json').write_text(json.dumps({
        'status': 'passed', 'source_commit': source, 'platform': args.platform,
        'machine': platform.platform(), 'architecture': platform.machine(), 'host_python': sys.version,
        'tools': {name: version(name) for name in ('cibuildwheel', 'abi3audit')},
        'wheels': records}, indent=2))


if __name__ == '__main__':
    main()
