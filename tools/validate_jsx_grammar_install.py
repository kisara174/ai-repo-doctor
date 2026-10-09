"""Validate a separately installed CLI against the fixed original R051 repository."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET

CASES = Path(__file__).resolve().parents[1] / 'evaluation/jsx-ampersand/cases.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(python, cli, repo, expected_version, out):
    out.mkdir(parents=True, exist_ok=False)
    cases = json.loads(CASES.read_text())
    receipts = []

    def run(name, command):
        result = subprocess.run([str(v) for v in command], cwd=out, capture_output=True, text=True, timeout=120)
        receipt = {'command': [str(v) for v in command], 'expected_exit': 0,
                   'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
        (out / (name + '.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
        receipts.append({'name': name, 'exit_code': result.returncode})
        require(result.returncode == 0, name + ': see command receipt')
        return result.stdout

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

    before_status = git('status', '--porcelain=v1')
    require(git('rev-parse', 'HEAD') == cases['commit'], 'Wrong fixed repository commit')
    require(git('rev-parse', 'HEAD^{tree}') == cases['tree'], 'Wrong fixed repository tree')
    paths = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z']).decode().split('\0')
    before = {p: digest(repo / p) for p in paths if p}
    require(all(before[p] == value for p, value in cases['files'].items()), 'Original target source changed')
    require(run('version', [cli, '--version']).strip() == 'repo-doctor ' + expected_version, 'Wrong CLI version')
    metadata = json.loads(run('metadata', [python, '-B', '-c',
        'import json,repo_doctor,ai_repo_doctor_grammars; from importlib.metadata import version; '
        'print(json.dumps({"product":version("ai-repo-doctor"),"native":version("ai-repo-doctor-grammars"),'
        '"product_path":repo_doctor.__file__,"native_path":ai_repo_doctor_grammars.__file__}))']))
    require(metadata['product'] == expected_version and metadata['native'] == '0.1.0', 'Wrong installed metadata')
    require(all('site-packages' in Path(metadata[k]).parts for k in ('product_path', 'native_path')),
            'Source or prototype module imported')

    def rd(name, *args):
        return json.loads(run(name, [cli, name, repo, *args, '--languages', 'javascript', '--json']))

    overview = rd('overview')
    require(overview['stats']['parse_errors'] == 0 and overview['parse_errors'] == [], 'Original parse errors remain')
    require(overview['stats']['symbols'] == cases['expected_symbols'], 'Unexpected symbol count')
    symbols = rd('symbols', '--query', '.js', '--limit', '100')['matches']
    by_id = {row['id']: row for row in symbols}
    require(len(symbols) == cases['expected_symbols'], 'Symbol search was truncated')
    for row in cases['old_symbols']:
        require(by_id.get(row['id']) == row, 'Existing symbol changed: ' + row['id'])
    require(set(by_id) - {r['id'] for r in cases['old_symbols']} == set(cases['expected_new_ids']),
            'Unexpected recovered symbols')
    sid = cases['symbol']
    require(sid in by_id and by_id[sid]['start_line'] == cases['declaration']['line'], 'Target not found at original line')
    context = rd('context', sid, '--max-lines', '120')
    quotes = 0
    for block in context['blocks']:
        # Independent LF oracle for this SHA-frozen repository, including literal &.
        lines = (repo / block['file']).read_bytes().decode('utf-8').split('\n')
        for row in block['lines']:
            require(row['text'] == lines[row['line'] - 1], 'Source quotation mismatch')
            quotes += 1
    require(quotes > 0, 'Empty target context')
    target = next(b for b in context['blocks'] if b['file'] == by_id[sid]['file'])
    url = next(r['text'] for r in target['lines'] if r['line'] == cases['url_line'])
    require('&emoji=&slug=' in url, 'Original URL was rewritten or missing')
    impact = rd('impact', sid, '--depth', '2')
    rd('map', '--out', out / 'map')
    map_data = json.loads((out / 'map/map.json').read_text())
    require('symbol:' + sid in {n['id'] for n in map_data['nodes']}, 'Recovered target absent from map')
    for name, view in map_data['views'].items():
        svg = ET.parse(out / 'map' / (name + '.svg'))
        edges = {node.get('data-edge-id') for node in svg.iter() if node.get('data-edge-id') is not None}
        require(edges == {e['id'] for e in view['edges']}, name + ' SVG projection mismatch')
    require(git('status', '--porcelain=v1') == before_status, 'Target Git state changed')
    require(all(digest(repo / p) == h for p, h in before.items()), 'Tracked source changed')
    summary = {'status': 'passed', 'version': expected_version, 'metadata': metadata,
               'source_commit': cases['commit'], 'target_source_sha256': cases['files'],
               'commands': receipts, 'symbols': len(symbols), 'old_symbols_unchanged': len(cases['old_symbols']),
               'parse_errors': 0, 'context_quotes_checked': quotes, 'context_quote_mismatches': 0,
               'affected_symbols': len(impact['affected_symbols']), 'impact_is_runtime_complete': False,
               'svg_projections_checked': len(map_data['views']), 'tracked_sources_unchanged': len(before)}
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('python', 'cli', 'repo', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--expected-version', required=True)
    args = parser.parse_args()
    try:
        # Resolving a venv Python symlink would launch the global interpreter.
        summary = validate(args.python.absolute(), args.cli.resolve(), args.repo.resolve(),
                           args.expected_version, args.out.resolve())
        print(json.dumps({'status': summary['status'], 'commands': len(summary['commands'])}))
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Installed JSX validation failed: {exc}\n')


if __name__ == '__main__':
    main()
