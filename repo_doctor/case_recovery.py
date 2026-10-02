"""Export a bounded, read-only archive without changing the original case."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from .case import TOOL_VERSION, _checked_directory, _validate_case, timestamp
from .report import render_report


MAX_RECOVERY_BYTES = 32 * 1024 * 1024


def _write_new(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def export_archive(source: Path, destination: Path) -> dict:
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Archive directory already exists; choose a new output directory')
    source = _checked_directory(Path(source)).resolve()
    destination = destination.resolve()
    if destination.is_relative_to(source):
        raise ValueError('Archive output must be outside the source case directory')
    with (source / 'case.json').open('rb') as stream:
        raw = stream.read(MAX_RECOVERY_BYTES + 1)
    if len(raw) > MAX_RECOVERY_BYTES:
        raise ValueError('Recovery input exceeds 32 MiB')
    case = _validate_case(json.loads(raw.decode('utf-8')))
    prefix = ('> 只读档案：全部原始记录保留于 original-case.json。\n'
              '> 本目录不是可续写任务；后续调查请新建普通 case。\n'
              '> 历史工具版本原样保留，下方视图由当前渲染器生成。\n\n')
    report = (prefix + render_report(case)).encode('utf-8')
    artifacts = {'original-case.json': raw, 'recovered-report.md': report}
    receipt = {
        'schema_version': 1, 'status': 'read-only-archive', 'created_at': timestamp(),
        'source': str(source), 'directory': str(destination), 'source_bytes': len(raw),
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'source_tool_version': case['tool_version'], 'export_tool_version': TOOL_VERSION,
        'files_sha256': {name: hashlib.sha256(content).hexdigest() for name, content in artifacts.items()},
    }
    # Inputs and views are ready before creating anything. The receipt is last,
    # so interrupted output cannot be mistaken for a completed archive.
    destination.mkdir(mode=0o700, parents=True)
    for name, content in artifacts.items():
        _write_new(destination / name, content)
    _write_new(destination / 'recovery.json', (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Export a complete read-only case archive (up to 32 MiB)')
    parser.add_argument('case', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(export_archive(args.case, args.out), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError) as exc:
        print(f'Recovery failed: {exc}. Output, if present, may be incomplete.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
