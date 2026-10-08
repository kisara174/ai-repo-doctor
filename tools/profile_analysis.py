"""Measure installed five-step workflows on generated, never-executed source."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time
from xml.etree import ElementTree


def write(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source(index):
    suffix = ('.py', '.js', '.ts')[index % 3]
    name, previous = f'{index:04d}', f'{index-3:04d}'
    if suffix == '.py':
        prefix = f'from m{previous} import entry_{previous}\n' if index >= 3 else ''
        value = f'entry_{previous}()' if index >= 3 else '0'
        text = prefix + f'def leaf_{name}():\n    return {value}\n\ndef entry_{name}():\n    return leaf_{name}()\n'
    else:
        # TS .js specifiers exercise the documented source-association policy.
        prefix = f'import {{ entry_{previous} }} from "./m{previous}.js";\n' if index >= 3 else ''
        value = f'entry_{previous}()' if index >= 3 else '0'
        text = prefix + f'export function leaf_{name}() {{ return {value}; }}\nexport function entry_{name}() {{ return leaf_{name}(); }}\n'
    return f'm{name}{suffix}', text


def profile(cli, out, sizes, runs):
    require(cli.is_absolute() and cli.is_file() and os.access(cli, os.X_OK), '--cli must be an absolute executable')
    require(out.is_absolute() and not out.exists() and not out.is_symlink(), '--out must be a new absolute directory')
    out.mkdir(parents=True)
    commands, workflows, samples = [], [], []
    env = {key: value for key, value in os.environ.items() if key not in {'PYTHONPATH', 'PYTHONHOME', 'DEEPSEEK_API_KEY'}}
    env['PYTHONDONTWRITEBYTECODE'] = '1'

    def run(label, argv, *, is_query=True):
        started = time.monotonic()
        row = dict(label=label, argv=list(map(str, argv)), cwd=str(out), expected_exit_code=0,
                   external_timeout_seconds=90, timeout_kind='profiler subprocess deadline')
        try:
            result = subprocess.run(row['argv'], cwd=out, env=env, capture_output=True,
                                    text=True, encoding='utf-8', timeout=90)
            row.update(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr, timed_out=False)
        except subprocess.TimeoutExpired:
            row.update(exit_code=None, stdout='', stderr='Profiler deadline expired; not a product cooperative-limit receipt', timed_out=True)
        row['duration_seconds'] = time.monotonic() - started
        record = f'{len(commands)+1:03d}-{label}.json'
        write(out / record, row)
        commands.append(dict(label=label, record=record, exit_code=row['exit_code'], expected_exit_code=0,
                             duration_seconds=row['duration_seconds'], timed_out=row['timed_out']))
        require(row['exit_code'] == 0 and not row['timed_out'], f'{label} failed: see {record}')
        require(not is_query or row['duration_seconds'] < 60, f'{label} exceeded reference-machine 60-second target')
        return row['stdout'], row['duration_seconds']

    try:
        version, _ = run('version', [cli, '--version'], is_query=False)
        runtime, _ = run('runtime', [cli.parent / 'python', '-B', '-c',
            "import json,sys,platform,repo_doctor;print(json.dumps({'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'import_path':repo_doctor.__file__}))"], is_query=False)
        for size in sizes:
            repo = out / f'sample-{size}'
            repo.mkdir()
            hashes = {}
            for index in range(size):
                name, text = source(index)
                path = repo / name
                path.write_text(text, encoding='utf-8')
                hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            options = ['--languages', 'python,javascript,typescript', '--json']
            for number in range(runs):
                label, total = f'{size}-run-{number+1}', 0.0
                def query(name, args):
                    nonlocal total
                    output, elapsed = run(label+'-'+name, [cli, name, repo, *args, *options])
                    total += elapsed
                    data = json.loads(output)
                    require(data['resource_limits']['timeout_kind'] == 'cooperative', 'resource metadata missing')
                    require(sum(data['analysis']['files_by_language'].values()) == size, 'not all generated source files analyzed')
                    return data
                overview = query('overview', [])
                require(overview['stats']['symbols'] == 2*size and overview['stats']['parse_errors'] == 0,
                        'generated fixture symbols or syntax changed')
                found = query('symbols', ['--query', 'leaf_0000'])['matches']
                require(len(found) == 1, 'target was not uniquely discovered')
                target = found[0]['id']
                context = query('context', [target, '--max-lines', '120'])
                require(context['blocks'] and context['symbol'] == target, 'context missing')
                impact = query('impact', [target, '--depth', '2'])
                require(any(row['symbol'] == 'm0000.py::entry_0000' for row in impact['affected_symbols']), 'known caller missing')
                mapped = query('map', ['--out', out / (label+'-map')])
                graph = json.loads(Path(mapped['map_json']).read_text())
                require(graph['limits'] == {'nodes': 200, 'edges': 500}, 'map view caps changed')
                require(Path(mapped['html']).is_file(), 'offline map missing')
                for key in ('structure_svg', 'relations_svg'):
                    require(ElementTree.parse(mapped[key]).getroot().tag.endswith('svg'), 'invalid SVG')
                require(total <= 120, f'{label} exceeded reference-machine 120-second five-step target')
                workflows.append(dict(size=size, run=number+1, phase='first' if number == 0 else 'repeat',
                                      duration_seconds=total, symbols=overview['stats']['symbols'],
                                      resolved_calls=overview['stats']['resolved_calls'], target=target))
                print(f'{label}: {total:.3f}s', flush=True)
            require(hashes == {name: hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in hashes}, 'generated target source changed')
            samples.append(dict(files=size, raw_bytes=sum((repo/name).stat().st_size for name in hashes),
                                source_hashes=hashes, target_code_executed=False, target_dependencies_installed=False))
        summary = dict(schema_version=1, status='passed', cli=str(cli.resolve()), version=version.strip(),
                       installed_runtime=json.loads(runtime), machine=platform.machine(), processor=platform.processor(),
                       runs=runs, samples=samples, workflows=workflows, commands=commands,
                       performance_claim='Recorded machine and generated samples only; no hard native-parser/RSS guarantee',
                       target_code_executed=False, target_dependencies_installed=False)
        write(out / 'summary.json', summary)
        return summary
    except Exception as exc:
        write(out / 'failure.json', dict(status='failed', error=str(exc), workflows=workflows, commands=commands))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--sizes', default='100,1000')
    parser.add_argument('--runs', type=int, choices=range(1, 11), default=4)
    args = parser.parse_args()
    try:
        sizes = [int(value) for value in args.sizes.split(',')]
        require(sizes and len(sizes) == len(set(sizes)) and all(1 <= value <= 5000 for value in sizes),
                '--sizes must contain unique file counts from 1 through 5000')
        profile(args.cli, args.out, sizes, args.runs)
    except (ValueError, OSError, json.JSONDecodeError, ElementTree.ParseError) as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    main()
