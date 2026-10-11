"""Independently validate installed 1.0.2 reliability behaviors; never run targets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


class Validation:
    def __init__(self, args):
        self.args, self.commands, self.results = args, [], []
        self.env = {k: v for k, v in os.environ.items()
                    if k not in {'PYTHONPATH', 'PYTHONHOME', 'DEEPSEEK_API_KEY'}}
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'

    def run(self, name, argv, expected=0):
        started = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=self.args.out, env=self.env,
                                capture_output=True, text=True, timeout=60)
        receipt = dict(name=name, argv=list(map(str, argv)), cwd=str(self.args.out),
                       exit_code=result.returncode, expected_exit_code=expected,
                       duration_seconds=time.monotonic()-started,
                       stdout=result.stdout, stderr=result.stderr)
        filename = f'{len(self.commands)+1:02d}-{name}.json'
        write(self.args.out / filename, receipt)
        self.commands.append(dict(name=name, record=filename, exit_code=result.returncode))
        require(result.returncode == expected, f'{name}: unexpected exit; see {filename}')
        if expected:
            require(not result.stdout and result.stderr, f'{name}: failure returned success output')
        return result.stdout

    def data(self, name, *args):
        return json.loads(self.run(name, [self.args.cli, *args, '--json']))

    def repo(self, name, files):
        root = self.args.out / name
        root.mkdir()
        for path, source in files.items():
            file = root / path
            require(file.resolve().is_relative_to(root.resolve()), 'fixture escapes repository')
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(source, encoding='utf-8')
        return root

    def check_edges(self, case):
        name = case['id']
        root = self.repo(name, case['files'])
        hashes = {path: hashlib.sha256((root/path).read_bytes()).hexdigest() for path in case['files']}
        pairs = case.get('forbidden_edges', []) or case['required_edges']
        caller, callee = pairs[0]
        self.data(name+'-overview', 'overview', root)
        matches = self.data(name+'-symbols', 'symbols', root, '--query', caller)['matches']
        require(any(row['id'] == caller for row in matches), f'{name}: caller missing')
        context = self.data(name+'-context', 'context', root, caller)
        impact = self.data(name+'-impact', 'impact', root, callee)
        result = self.data(name+'-map', 'map', root, '--out', self.args.out / (name+'-map'))
        graph = json.loads(Path(result['map_json']).read_text())
        context_edges = {(e['caller'], e['callee']) for e in context['call_evidence']}
        map_edges = {(e['source'].removeprefix('symbol:'), e['target'].removeprefix('symbol:'))
                     for e in graph['edges'] if e['kind'] == 'call'}
        affected = {row['symbol'] for row in impact['affected_symbols']}
        for pair in case.get('forbidden_edges', []):
            require(tuple(pair) not in context_edges and tuple(pair) not in map_edges,
                    f'{name}: incorrect call edge remains')
            require(pair[0] not in affected, f'{name}: incorrect impact remains')
        for pair in case.get('required_edges', []):
            require(tuple(pair) in context_edges and tuple(pair) in map_edges,
                    f'{name}: required call edge was lost')
            require(pair[0] in affected, f'{name}: required impact was lost')
        require(hashes == {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in case['files']},
                'target source changed')
        self.results.append({'id': name, 'status': 'passed', 'outputs': ['overview','symbols','context','impact','map']})

    def check_mutation(self, case):
        code = '''import json,sys
from pathlib import Path
from unittest.mock import patch
from repo_doctor import cli,index
root=Path(sys.argv[1]); argv=json.loads(sys.argv[2]); replacement=sys.argv[3]
parse=index.parse_python_file
def edited(*args,**kwargs):
    result=parse(*args,**kwargs)
    (root/'app.py').write_text(replacement,encoding='utf-8')
    return result
with patch.object(index,'parse_python_file',side_effect=edited):
    raise SystemExit(cli.main(argv))
'''
        for command in ('overview','symbols','context','impact','map'):
            root = self.repo('F04-'+command, case['files'])
            argv = [command, str(root)]
            artifact = self.args.out / ('F04-'+command+'-artifact')
            if command == 'symbols':
                argv += ['--query', 'original']
            elif command in ('context','impact'):
                argv += [case['requested_symbol']]
            if command == 'context':
                argv += ['--snapshot-out', str(artifact)]
            elif command == 'map':
                argv += ['--out', str(artifact)]
            argv += ['--json']
            self.run('F04-'+command, [self.args.python, '-B', '-c', code, root,
                                     json.dumps(argv), case['mutation']], expected=2)
            require(not artifact.exists(), 'source mutation left a successful artifact')
        self.results.append({'id': 'F04', 'status': 'passed', 'controlled_edit': True,
                             'target_code_executed': False})

    def check_language(self, case, has_extra):
        if not has_extra:
            self.results.append({'id': case['id'], 'status': 'not-applicable',
                                 'reason': 'base install intentionally has no optional JS/TS backend'})
            return
        for language, filename, display in [('javascript','app.js','JavaScript'),
                                            ('typescript','app.ts','TypeScript')]:
            root = self.repo('F06-'+language, {filename: next(iter(case['files'].values()))})
            overview = self.data('F06-'+language, 'overview', root, '--languages', language)
            lead = overview['review_leads'][0]
            require(display in lead['subject'] and 'Python' not in lead['reason'], 'wrong language lead')
            require('Tree-sitter' in lead['reason'], 'wrong backend lead')
        self.results.append({'id': 'F06', 'status': 'passed', 'languages': ['javascript','typescript']})

    def positives(self):
        source = ('def leaf():\n    return 1\n'
                  'def entry():\n    return leaf()\n'
                  'def outer():\n    def nested():\n        return 1\n    return nested()\n'
                  'class Worker:\n    def work(self):\n        return 1\n'
                  '    def caller(self):\n        return self.work()\n')
        self.check_edges({'id':'positive','files':{'app.py':source},'required_edges':[
            ['app.py::entry','app.py::leaf']]})
        root = self.args.out / 'positive'
        for caller, callee in [('outer','outer.nested'),('Worker.caller','Worker.work')]:
            context = self.data('positive-'+caller, 'context', root, 'app.py::'+caller)
            require(any(e['caller'] == 'app.py::'+caller and e['callee'] == 'app.py::'+callee
                        for e in context['call_evidence']), 'stable binding lost')
        snapshot = self.args.out / 'positive-snapshot.json'
        self.data('positive-snapshot', 'context', root, 'app.py::entry', '--snapshot-out', snapshot)
        require(json.loads(snapshot.read_text())['context']['symbol'] == 'app.py::entry', 'snapshot failed')

    def validate(self):
        require(all(p.is_absolute() for p in (self.args.python,self.args.cli,self.args.out,self.args.cases)),
                'all input/output paths must be absolute')
        require(not self.args.out.exists() and not self.args.out.is_symlink(), 'output already exists')
        self.args.out.mkdir(parents=True)
        metadata = json.loads(self.run('metadata', [self.args.python,'-B','-c',
            "import json,sys,repo_doctor,importlib.util; from importlib.metadata import version; "
            "print(json.dumps({'version':version('ai-repo-doctor'),'prefix':sys.prefix,"
            "'import_path':repo_doctor.__file__,'js':importlib.util.find_spec('ai_repo_doctor_grammars') is not None}))"]))
        imported = Path(metadata['import_path']).resolve()
        require(metadata['version'] == self.args.expected_version, 'wrong installed metadata')
        require('site-packages' in imported.parts and imported.is_relative_to(Path(metadata['prefix']).resolve()),
                'product imported from checkout instead of installation')
        require(self.run('version',[self.args.cli,'--version']).strip() == 'repo-doctor '+self.args.expected_version,
                'wrong installed CLI')
        cases = json.loads(self.args.cases.read_text())['cases']
        require({case['id'] for case in cases} == {'F01','F02','F03','F04','F05','F06'}, 'wrong case set')
        for case in cases:
            if case['id'] == 'F04': self.check_mutation(case)
            elif case['id'] == 'F06': self.check_language(case, metadata['js'])
            else: self.check_edges(case)
        self.positives()
        write(self.args.out/'receipt.json', {'status':'passed','version':metadata['version'],
              'metadata':metadata,'cases':self.results,'commands':self.commands,
              'target_code_executed':False,'target_dependencies_installed':False})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('python','cli','cases','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expected-version',required=True)
    args = parser.parse_args(argv)
    validator = Validation(args)
    try:
        validator.validate()
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        # Record only when this validator created the new output directory.
        if validator.commands:
            write(args.out/'failure.json', {'status':'failed','error':str(exc),'commands':validator.commands})
        print(str(exc),file=sys.stderr)
        return 2
    print(f'Reliability install: {len(validator.commands)} commands passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
