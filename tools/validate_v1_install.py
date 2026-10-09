"""Verify a separately installed core CLI and its bound Skill, outside the checkout."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from xml.etree import ElementTree


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


class Validation:
    def __init__(self, mode, python, cli, expected_version, out):
        self.mode, self.python, self.cli = mode, python, cli
        self.version, self.out = expected_version, out
        self.commands = []
        self.created = False
        self.env = {key: value for key, value in os.environ.items()
                    if key not in {'PYTHONPATH', 'PYTHONHOME', 'DEEPSEEK_API_KEY'}}
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'

    def run(self, name, argv, expected=0):
        argv = list(map(str, argv))
        started = time.monotonic()
        result = subprocess.run(argv, cwd=self.out, env=self.env, capture_output=True,
                                text=True, encoding='utf-8', timeout=30)
        row = dict(name=name, argv=argv, cwd=str(self.out), exit_code=result.returncode,
                   expected_exit_code=expected, duration_seconds=time.monotonic()-started,
                   stdout=result.stdout, stderr=result.stderr)
        filename = f'{len(self.commands)+1:02d}-{name}.json'
        write(self.out / filename, row)
        self.commands.append(dict(name=name, record=filename, exit_code=result.returncode,
                                  expected_exit_code=expected))
        require(result.returncode == expected, f'{name}: unexpected exit; see {filename}')
        if expected != 0:
            require(not result.stdout and result.stderr, f'{name}: error looked like successful JSON')
        return result.stdout

    def rd(self, name, *args, expected=0):
        return self.run(name, [self.cli, *args], expected)

    def data(self, name, *args):
        return json.loads(self.rd(name, *args, '--json'))

    def workflow(self, repo, label, query, languages):
        options = ['--languages', languages]
        overview = self.data(label+'-overview', 'overview', repo, *options)
        matches = self.data(label+'-symbols', 'symbols', repo, '--query', query, *options)['matches']
        require(len(matches) == 1, f'{label}: target is not unique')
        symbol = matches[0]['id']
        context = self.data(label+'-context', 'context', repo, symbol, '--max-lines', '120', *options)
        require(context['symbol'] == symbol and context['blocks'], f'{label}: context missing')
        require(sum(len(block['lines']) for block in context['blocks']) <= 120, 'context budget exceeded')
        impact = self.data(label+'-impact', 'impact', repo, symbol, '--depth', '2', *options)
        expected_caller = 'app.py::entry' if label == 'python' else 'consumer.ts::call'
        require(any(row['symbol'] == expected_caller and row['distance'] == 1
                    for row in impact['affected_symbols']), f'{label}: direct caller missing')
        directory = self.out / (label+'-map')
        result = self.data(label+'-map', 'map', repo, '--out', directory, *options)
        paths = [Path(result[key]) for key in ('map_json', 'html', 'structure_svg', 'relations_svg')]
        require(all(path.parent == directory and path.is_file() for path in paths), 'map artifact missing')
        graph = json.loads(paths[0].read_text())
        require(graph['limits'] == {'nodes': 200, 'edges': 500}, 'map projection limits changed')
        for path in paths[2:]:
            require(ElementTree.parse(path).getroot().tag.endswith('svg'), 'invalid SVG')
        original = {str(path): digest(path) for path in paths}
        self.rd(label+'-map-no-overwrite', 'map', repo, '--out', directory, *options, '--json', expected=2)
        require({str(path): digest(path) for path in paths} == original, 'existing map was changed')
        require(overview['analysis']['requested_languages'] == languages.split(','), 'language selection mismatch')
        return original

    def validate(self):
        require(all(path.is_absolute() for path in (self.python, self.cli, self.out)), 'paths must be absolute')
        require(self.python.is_file() and self.cli.is_file(), 'installed Python/CLI missing')
        require(not self.out.exists() and not self.out.is_symlink(), 'output already exists')
        self.out.mkdir(parents=True)
        self.created = True
        code = (
            "import hashlib,importlib.util,json,sys,repo_doctor;"
            "from importlib.metadata import version;from importlib.resources import files;"
            "print(json.dumps({'version':version('ai-repo-doctor'),'prefix':sys.prefix,"
            "'import_path':repo_doctor.__file__,'python':sys.version,"
            "'skill_sha256':hashlib.sha256(files('repo_doctor').joinpath('resources/skill/SKILL.md').read_bytes()).hexdigest(),"
            "'backends':{name:importlib.util.find_spec(name) is not None for name in "
            "('tree_sitter','ai_repo_doctor_grammars','tree_sitter_typescript')}}))"
        )
        metadata = json.loads(self.run('metadata', [self.python, '-B', '-c', code]))
        require(metadata['version'] == self.version, 'wrong installed version')
        imported = Path(metadata['import_path']).resolve()
        require('site-packages' in imported.parts and imported.is_relative_to(Path(metadata['prefix']).resolve()),
                'import did not come from the selected installed environment')
        require(all(metadata['backends'].values()) if self.mode == 'js'
                else not any(metadata['backends'].values()), 'base/js backend isolation failed')
        require(self.rd('version', '--version').strip() == f'repo-doctor {self.version}', 'CLI version mismatch')
        repo = self.out / 'repo'
        repo.mkdir()
        sources = {
            'app.py': 'def leaf(value):\n    return value + 1\n\ndef entry(value):\n    return leaf(value)\n',
            'core.ts': 'export function add(value: number) { return value + 1; }\n',
            'consumer.ts': "import { add } from './core.ts';\nexport function call(value: number) { return add(value); }\n",
        }
        for name, source in sources.items():
            (repo / name).write_text(source, encoding='utf-8')
        before = {name: digest(repo / name) for name in sources}
        maps = self.workflow(repo, 'python', 'leaf', 'python')
        if self.mode == 'js':
            maps.update(self.workflow(repo, 'mixed', 'add', 'python,javascript,typescript'))
        else:
            self.rd('missing-extra', 'overview', repo, '--languages', 'typescript', '--json', expected=2)
        skill = self.out / 'bound skill'
        self.rd('skill-export', 'skill', 'export', '--out', skill, '--cli', self.cli)
        binding = json.loads((skill / 'installation.json').read_text())
        require(binding == {'schema_version': 1, 'cli': str(self.cli.resolve()), 'version': self.version},
                'Skill is not bound to the verified CLI')
        require(digest(skill / 'SKILL.md') == metadata['skill_sha256'], 'Skill differs from installed resource')
        skill_before = {name: digest(skill / name) for name in ('SKILL.md', 'installation.json')}
        self.rd('skill-no-overwrite', 'skill', 'export', '--out', skill, '--cli', self.cli, expected=2)
        require({name: digest(skill / name) for name in skill_before} == skill_before, 'existing Skill changed')
        require({name: digest(repo / name) for name in sources} == before, 'target source changed')
        summary = dict(status='passed', mode=self.mode, version=self.version, installed_metadata=metadata,
                       python=str(self.python), cli=str(self.cli), commands=self.commands,
                       map_sha256=maps, skill_binding=binding, source_sha256=before,
                       target_code_executed=False, target_dependencies_installed=False,
                       fresh_codex_session_verified=False)
        write(self.out / 'summary.json', summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('base', 'js'), required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--cli', type=Path, required=True)
    parser.add_argument('--expected-version', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    validator = Validation(args.mode, args.python, args.cli, args.expected_version, args.out)
    try:
        summary = validator.validate()
    except (ValueError, OSError, UnicodeError, KeyError, StopIteration,
            ElementTree.ParseError, subprocess.TimeoutExpired) as exc:
        if validator.created:
            write(args.out / 'failure.json', {'status': 'failed', 'error': str(exc), 'commands': validator.commands})
        print(f'Installed v1 validation failed: {exc}', file=sys.stderr)
        return 2
    print(json.dumps({'status': summary['status'], 'mode': args.mode,
                      'version': summary['version'], 'commands': len(summary['commands'])}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
