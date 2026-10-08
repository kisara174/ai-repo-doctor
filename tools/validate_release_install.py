"""Validate an installed release through its CLI, outside the source checkout."""

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree


EXPECTED_VERSION = '1.0.0.dev1'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_hashes(directory: Path) -> dict:
    return {name: file_hash(directory / name) for name in ('case.json', 'report.md')}


class InstalledValidation:
    def __init__(self, python: Path, cli: Path, out: Path, expected_version: str = EXPECTED_VERSION):
        self.python, self.cli, self.out = python, cli, out
        self.expected_version = expected_version
        self.env = dict(os.environ)
        self.env.pop('PYTHONPATH', None)
        self.env.pop('DEEPSEEK_API_KEY', None)
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'
        self.commands = []

    def run(self, name: str, argv: list, expected: int = 0) -> str:
        argv = list(map(str, argv))
        result = subprocess.run(argv, cwd=self.out, env=self.env, capture_output=True,
                                text=True, encoding='utf-8', timeout=120, check=False)
        record = dict(name=name, argv=argv, cwd=str(self.out), exit_code=result.returncode,
                      expected_exit_code=expected,
                      stdout=result.stdout, stderr=result.stderr)
        log = f'{len(self.commands) + 1:02d}-{name}.json'
        write_json(self.out / log, record)
        self.commands.append(dict(name=name, exit_code=result.returncode,
                                  expected_exit_code=expected, log=log))
        require(result.returncode == expected,
                f'{name}: expected exit {expected}, got {result.returncode}; see {log}')
        return result.stdout

    def rd(self, name: str, *args, expected: int = 0) -> str:
        return self.run(name, [self.cli, *args], expected)

    def check_report(self, name: str, case: Path, repaired: bool) -> None:
        text = self.rd(name, 'report', 'show', case)
        require(('有修复证据' in text) == repaired, f'{name}: incorrect repair evidence')
        if not repaired:
            require('仍需复核' in text, f'{name}: missing pending review state')

    def validate(self) -> dict:
        metadata = json.loads(self.run('metadata', [self.python, '-B', '-c',
            "import json, repo_doctor; from importlib.metadata import version, metadata; "
            "print(json.dumps({'version': version('ai-repo-doctor'), "
            "'import_path': repo_doctor.__file__, "
            "'requires_dist': metadata('ai-repo-doctor').get_all('Requires-Dist') or []}))"]))
        require(metadata['version'] == self.expected_version, 'wrong installed distribution version')
        require('site-packages' in Path(metadata['import_path']).parts, 'source checkout imported')
        dependencies = metadata['requires_dist']
        require(len(dependencies) == 3 and all('extra == "js"' in row or "extra == 'js'" in row for row in dependencies),
                'unexpected unconditional runtime dependencies')
        version = self.rd('version', '--version').strip()
        require(version == f'repo-doctor {self.expected_version}', 'CLI version mismatch')

        repo, case = self.out / 'repo', self.out / 'case'
        repo.mkdir()
        source = repo / 'app.py'
        original_source = 'def value():\n    return 1\n\ndef entry():\n    return value()\n'
        source.write_text(original_source, encoding='utf-8')
        overview = json.loads(self.rd('overview', 'overview', repo, '--json'))
        require(overview['stats']['python_files'] == 1, 'overview lost the controlled source')
        matches = json.loads(self.rd('symbols', 'symbols', repo, '--query', 'value', '--json'))
        symbol = next((item['id'] for item in matches['matches'] if item['id'] == 'app.py::value'), None)
        require(symbol is not None, 'symbol search failed')
        snapshot = self.out / 'context.json'
        self.rd('context', 'context', repo, symbol, '--snapshot-out', snapshot, '--json')
        impact = json.loads(self.rd('impact', 'impact', repo, symbol, '--depth', '2', '--json'))
        require(any(item['symbol'] == 'app.py::entry' for item in impact['affected_symbols']),
                'impact lost entry -> value')
        map_dir = self.out / 'map'
        self.rd('map', 'map', repo, '--out', map_dir, '--json')
        names = {'map.html', 'map.json', 'structure.svg', 'relations.svg'}
        require({p.name for p in map_dir.iterdir()} == names, 'map must have exactly four artifacts')
        for name in ('structure.svg', 'relations.svg'):
            ElementTree.parse(map_dir / name)
        created = json.loads(self.rd('create-case', 'report', 'create', repo, '--out', case, '--json'))
        require(created['tool_version'] == self.expected_version, 'new case version mismatch')
        finding = dict(title='Controlled value contract', category='behavior', confidence=0.9,
                       reasoning='This controlled fixture requires value() == 2.',
                       impact='entry calls value', suggested_fix='Change value and check explicitly',
                       evidence=[dict(file='app.py', start_line=2, end_line=2,
                                      quote='    return 1', symbol=symbol)])
        finding_path = self.out / 'findings.json'
        write_json(finding_path, {'findings': [finding]})
        self.rd('import', 'findings', 'import', case, '--from', finding_path,
                '--context', snapshot, '--producer', 'codex')
        require(read_json(case / 'case.json')['issues'][0]['id'] == 'A-001', 'unstable issue ID')

        command_a = [self.python, '-B', '-c', 'import app; assert app.value() == 2']
        command_b = [self.python, '-B', '-c', 'import app; assert app.entry() == 2']
        self.rd('a-before', 'verify', case, 'A-001', '--phase', 'before', '--', *command_a, expected=1)
        source.write_text(original_source.replace('return 1', 'return 2'), encoding='utf-8')
        self.rd('a-after', 'verify', case, 'A-001', '--phase', 'after', '--', *command_a)
        self.rd('associate-a', 'issue', case, 'A-001', '--status', 'resolved', '--actor', 'codex',
                '--note', 'This command checks the controlled value contract', '--related-test')
        self.check_report('normal-report', case, repaired=True)

        legacy = self.out / 'legacy-case'
        legacy.mkdir()
        legacy_data = read_json(case / 'case.json')
        legacy_data['tool_version'] = '0.5.0'
        legacy_data['issues'][0]['human_history'][-1].pop('related_test_argv')
        write_json(legacy / 'case.json', legacy_data)
        (legacy / 'report.md').write_bytes((case / 'report.md').read_bytes())
        legacy_before = case_hashes(legacy)
        old = json.loads(self.rd('old-case', 'report', 'show', legacy, '--json'))
        require(old['tool_version'] == '0.5.0', 'old source version changed')
        self.check_report('old-single-command-report', legacy, repaired=True)
        require(case_hashes(legacy) == legacy_before, 'reading changed the old case')

        source.write_text('def value():\n    return 2\n\ndef entry():\n    return 0\n', encoding='utf-8')
        self.rd('b-before', 'verify', case, 'A-001', '--phase', 'before', '--', *command_b, expected=1)
        self.rd('a-after-new-cycle', 'verify', case, 'A-001', '--phase', 'after', '--', *command_a)
        self.check_report('current-cycle-report', case, repaired=False)
        source.write_text('def value():\n    return 2\n\ndef entry():\n    return 2\n', encoding='utf-8')
        self.rd('b-after', 'verify', case, 'A-001', '--phase', 'after', '--', *command_b)
        self.check_report('unassociated-b-report', case, repaired=False)
        self.rd('associate-b', 'issue', case, 'A-001', '--status', 'resolved', '--actor', 'codex',
                '--note', 'This new command checks the controlled entry contract', '--related-test')
        self.check_report('associated-b-report', case, repaired=True)
        require(read_json(case / 'case.json')['issues'][0]['human_history'][-1]['related_test_argv']
                == list(map(str, command_b)), 'review bound to wrong command')

        stale_before = case_hashes(case)
        self.rd('stale-snapshot', 'findings', 'import', case, '--from', finding_path,
                '--context', snapshot, '--producer', 'codex', expected=2)
        require(case_hashes(case) == stale_before, 'stale import changed existing case')

        large_repo, capacity_case = self.out / 'large-repo', self.out / 'capacity-case'
        large_repo.mkdir()
        (large_repo / 'app.py').write_text(original_source, encoding='utf-8')
        large_snapshot = self.out / 'large-context.json'
        self.rd('capacity-case', 'report', 'create', large_repo, '--out', capacity_case)
        self.rd('capacity-context', 'context', large_repo, symbol, '--snapshot-out', large_snapshot)
        large_finding = {**finding, 'reasoning': 'r' * 800000}
        large_path = self.out / 'large-findings.json'
        write_json(large_path, {'findings': [large_finding]})
        require(large_path.stat().st_size < 1024 * 1024, 'finding input is not independently legal')
        import_args = ('findings', 'import', capacity_case, '--from', large_path,
                       '--context', large_snapshot, '--producer', 'codex')
        for number in range(5):
            self.rd(f'capacity-import-{number + 1}', *import_args)
        capacity_before = case_hashes(capacity_case)
        self.rd('capacity-import-6', *import_args, expected=2)
        require(case_hashes(capacity_case) == capacity_before, 'oversize write damaged saved files')
        saved = json.loads(self.rd('capacity-reopen', 'report', 'show', capacity_case, '--json'))
        require(len(saved['issues']) == 5, 'previous saved case did not reopen completely')

        historical = self.out / 'historical-large-case'
        historical.mkdir()
        history = copy.deepcopy(saved)
        history['tool_version'] = '0.5.0'
        issue = copy.deepcopy(history['issues'][-1])
        issue['id'] = 'A-006'
        history['issues'].append(issue)
        attempt = copy.deepcopy(history['imports'][-1])
        attempt['accepted_issue_ids'] = ['A-006']
        history['imports'].append(attempt)
        write_json(historical / 'case.json', history)
        (historical / 'report.md').write_text('Historical view retained unchanged.\n', encoding='utf-8')
        require((historical / 'case.json').stat().st_size > 8 * 1024 * 1024,
                'historical fixture did not reproduce the oversize defect')
        historical_before = case_hashes(historical)
        archive = self.out / 'archive'
        recovery = json.loads(self.run('case-recovery', [self.python, '-B', '-m',
                              'repo_doctor.case_recovery', historical, '--out', archive]))
        require(case_hashes(historical) == historical_before, 'recovery modified original files')
        require((archive / 'original-case.json').read_bytes() == (historical / 'case.json').read_bytes(),
                'recovery did not preserve complete original bytes')
        require(len(read_json(archive / 'original-case.json')['issues']) == 6, 'recovery lost issues')
        require(recovery == read_json(archive / 'recovery.json'), 'recovery receipt mismatch')
        require(recovery['source_tool_version'] == '0.5.0'
                and recovery['export_tool_version'] == self.expected_version, 'recovery version mismatch')
        for name, digest in recovery['files_sha256'].items():
            require(file_hash(archive / name) == digest, 'recovery artifact hash mismatch')
        report_text = (archive / 'recovered-report.md').read_text(encoding='utf-8')
        require('只读档案' in report_text and all(f'A-{i:03d}' in report_text for i in range(1, 7)),
                'read-only report is incomplete')

        return dict(version=self.expected_version, site_packages_import=True,
                    report_version_matches=True, normal_offline_flow=True,
                    current_cycle_guard=True, related_command_guard=True,
                    oversize_write_preserved_case=True, oversize_write_preserved_report=True,
                    saved_case_reopened=True, read_only_recovery_complete=True,
                    old_case_unchanged=True, stale_snapshot_rejected=True, map_files=4,
                    installed_metadata=metadata, python=str(self.python), cli=str(self.cli),
                    evidence_directory=str(self.out), commands=self.commands,
                    capacity_hashes=capacity_before, original_history_hashes=historical_before)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--cli', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--expected-version', default=EXPECTED_VERSION)
    args = parser.parse_args()
    try:
        require(all(path.is_absolute() for path in (args.python, args.cli, args.out)),
                'all paths must be absolute')
        require(args.python.is_file() and args.cli.is_file(), 'installed Python/CLI missing')
        require(not args.out.exists() and not args.out.is_symlink(), 'evidence output already exists')
        args.out.mkdir(mode=0o700, parents=True)
        validator = InstalledValidation(args.python, args.cli, args.out.resolve(), args.expected_version)
        receipt = validator.validate()
        write_json(args.out / 'receipt.json', receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f'Installed release validation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
