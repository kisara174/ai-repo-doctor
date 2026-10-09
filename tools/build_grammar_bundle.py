"""Bundle the two audited, same-commit companion wheels; never builds or publishes."""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZipInfo, ZIP_STORED


def require(condition, message):
    if not condition:
        raise ValueError(message)


def build(wheelhouse: Path, out: Path, source_commit: str):
    require(re.fullmatch(r'[0-9a-f]{40}', source_commit) is not None, 'Expected full source commit')
    root = Path(__file__).resolve().parents[1]
    expected = json.loads((root / 'backends/jsx-grammars/provenance.json').read_text())
    receipts = [json.loads(p.read_text()) for p in wheelhouse.rglob('receipt.json')]
    require(len(receipts) == 2, 'Expected two native build receipts')
    require({r['platform'] for r in receipts} == {'linux', 'macos'}, 'Missing or duplicate platform receipt')
    recorded = {}
    for receipt in receipts:
        require(receipt['status'] == 'passed' and receipt['source_commit'] == source_commit,
                'Wheel receipt belongs to another source or failed build')
        require(len(receipt['wheels']) == 1, 'Unexpected native wheel count')
        record = receipt['wheels'][0]
        require(record['provenance'] == expected, 'Wheel frozen sources differ from checkout')
        recorded[record['file']] = (receipt['platform'], record['sha256'])
    wheels = sorted(wheelhouse.rglob('*.whl'))
    require(len(wheels) == 2 and {p.name for p in wheels} == set(recorded), 'Wheel set differs from receipts')
    records = []
    for wheel in wheels:
        platform, digest = recorded[wheel.name]
        require(hashlib.sha256(wheel.read_bytes()).hexdigest() == digest, 'Wheel checksum differs from receipt')
        require(wheel.name.startswith('ai_repo_doctor_grammars-0.1.0-cp311-abi3-'), 'Unexpected name/version/ABI')
        if platform == 'linux':
            require('manylinux' in wheel.name and wheel.name.endswith('_x86_64.whl') and
                    ('manylinux_2_17_' in wheel.name or 'manylinux2014_' in wheel.name), 'Unsupported Linux tag')
        else:
            require(wheel.name.endswith('-macosx_11_0_arm64.whl'), 'Unsupported macOS tag')
        with ZipFile(wheel) as archive:
            names = archive.namelist()
            metadata = BytesParser().parsebytes(archive.read(next(n for n in names if n.endswith('.dist-info/METADATA'))))
            require(metadata['Name'] == 'ai-repo-doctor-grammars' and metadata['Version'] == '0.1.0', 'Wrong wheel metadata')
            require(metadata['License-Expression'] == 'MIT', 'Missing MIT metadata')
            require(all(any(n.endswith('/' + license) for n in names)
                        for license in ('JAVASCRIPT-LICENSE', 'TYPESCRIPT-LICENSE')), 'Upstream license missing')
            require(json.loads(archive.read('ai_repo_doctor_grammars/provenance.json')) == expected, 'Wrong embedded provenance')
        records.append({'file': wheel.name, 'platform': platform, 'sha256': digest})
    manifest = {'schema_version': 1, 'version': '0.1.0', 'source_commit': source_commit,
                'wheels': records, 'build_receipts': sorted(receipts, key=lambda r: r['platform'])}
    out.parent.mkdir(parents=True, exist_ok=True)
    payloads = {p.name: p.read_bytes() for p in wheels}
    payloads['manifest.json'] = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    with out.open('xb') as stream, ZipFile(stream, 'w', compression=ZIP_STORED) as archive:
        for name, body in sorted(payloads.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, body)
    checksum = out.with_name(out.name + '.sha256')
    with checksum.open('x') as stream:
        stream.write(hashlib.sha256(out.read_bytes()).hexdigest() + '  ' + out.name + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheelhouse', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    try:
        manifest = build(args.wheelhouse, args.out, args.source_commit)
        print(json.dumps({'status': 'passed', 'wheels': len(manifest['wheels'])}))
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        parser.exit(1, f'Native bundle rejected: {exc}\n')


if __name__ == '__main__':
    main()
