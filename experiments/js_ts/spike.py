"""Disposable JS/TS syntax experiment. Never imports or executes target code."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath


from repo_doctor.js_ts import extract


def source_text(root, path, identity):
    from repo_doctor.source import read_source
    from repo_doctor.languages import language_for_path
    return read_source(root, path, identity, language=language_for_path(path))


def path_language(path):
    if path.endswith(('.js', '.mjs')):
        return 'javascript'
    if path.endswith('.ts') and not path.endswith('.d.ts'):
        return 'typescript'
    return None


def build_spike(root, languages):
    from repo_doctor.model import RepoIndex, FileRecord, Symbol, ParseError, ImportEdge, OverloadSignature
    from repo_doctor.scanner import discover_files
    root = Path(root).resolve()
    paths, mode = discover_files(root)
    st = root.stat(follow_symlinks=False)
    index = RepoIndex(root, mode, (st.st_dev, st.st_ino))
    parsed = {}
    source_hash = hashlib.sha256()
    for path in paths:
        language = path_language(path)
        if language not in languages:
            continue
        source = source_text(root, path, index.root_identity)
        source_hash.update(path.encode() + b'\0' + source.encode() + b'\0')
        item = extract(source, file=path, language=language)
        parsed[path] = item
        lines = source.splitlines()
        parts = PurePosixPath(path).parts
        index.files.append(FileRecord(path, len(lines), sum(bool(l.strip()) for l in lines),
                                      'test' in parts or 'tests' in parts or PurePosixPath(path).name.startswith('test_')))
        if item['error']:
            index.parse_errors.append(ParseError(**item['error']))
        for s in item['symbols']:
            if s['id'] in index.symbols:
                index.ambiguous_symbols.add(s['id'])
            else:
                values = {**s, 'local_bindings': frozenset(s['local_bindings']),
                          'overloads': tuple(OverloadSignature(**o) for o in s['overloads'])}
                index.symbols[s['id']] = Symbol(**values)
    for sid in index.ambiguous_symbols:
        del index.symbols[sid]
    path_set = set(paths)
    limits = [l for item in parsed.values() for l in item['limits']]
    for path in paths:
        if path.endswith(('.jsx', '.tsx', '.cjs', '.mts', '.cts', '.d.ts')):
            limits.append({'file': path, 'line': None, 'reason': 'unsupported-source-kind',
                           'message': 'Path is displayed; this source kind is not parsed in the preview scope'})
    for path, item in parsed.items():
        for ref in item['esm_imports'] + item['esm_exports']:
            spec = ref['specifier']
            if spec is None:
                continue
            reason = 'external-or-alias'
            target = None
            if spec.startswith(('./', '../')) and '\\' not in spec:
                import posixpath
                candidate = posixpath.normpath(posixpath.join(posixpath.dirname(path), spec))
                options = [candidate]
                if path.endswith('.ts') and spec.endswith('.js'):
                    stem = candidate[:-3]
                    options = [stem + suffix for suffix in ('.ts', '.tsx', '.d.ts', '.js', '.jsx')]
                matches = [n for n in options if n in path_set]
                if len(matches) == 1 and matches[0] in parsed and parsed[matches[0]]['error'] is None:
                    target, reason = matches[0], 'unique-local-source'
                else:
                    reason = 'ambiguous-or-unsupported-local-source'
            if target:
                edge = ImportEdge(path, target, ref['start_line'])
                if edge not in index.import_edges:
                    index.import_edges.append(edge)
            ref.update(resolved_file=target, resolution_kind=reason)
            if not target:
                limits.append({'file': path, 'line': ref['start_line'], 'reason': reason, 'message': 'Module ' + spec + ' was not resolved'})
    analysis = {'schema_version': 1, 'requested_languages': list(languages),
                'files_by_language': {l: sum(path_language(p) == l for p in parsed) for l in ('python', 'javascript', 'typescript')},
                'capabilities': {l: ['symbols', 'esm-file-imports', 'context'] for l in languages},
                'limits': sorted(limits, key=lambda l: (l['file'], l['line'] or 0, l['reason']))[:50],
                'limits_omitted': max(0, len(limits) - 50),
                'scope': 'experimental static selected source languages; calls not supported; no runtime completeness'}
    return index, parsed, analysis, source_hash.hexdigest()


def context(index, parsed, sid, includes, max_lines):
    if sid not in index.symbols:
        raise ValueError('Unknown or ambiguous symbol: ' + sid)
    if not 1 <= max_lines <= 120:
        raise ValueError('max-lines must be between 1 and 120')
    blocks, remaining, seen = [], max_lines, set()
    def add(file, start, end, relation, symbol=None):
        nonlocal remaining
        key = (file, start, end)
        if key in seen:
            return
        seen.add(key)
        lines = source_text(index.root, file, index.root_identity).splitlines()
        take = min(remaining, end - start + 1)
        selected = [{'line': n, 'text': lines[n - 1]} for n in range(start, start + take)]
        blocks.append({'symbol': symbol, 'relation': relation, 'file': file,
                       'start_line': start, 'end_line': start + take - 1 if take else start,
                       'lines': selected, 'truncated': take < end - start + 1})
        remaining -= take
    selected = [index.symbols[sid]]
    for include in includes:
        if include not in index.symbols:
            raise ValueError('Unknown include symbol: ' + include)
        if include != sid:
            selected.append(index.symbols[include])
    for i, symbol in enumerate(selected):
        add(symbol.file, symbol.start_line, symbol.end_line, 'target' if i == 0 else 'include', symbol.id)
        header = parsed[symbol.file]['class_header_spans'].get(symbol.parent)
        if header:
            add(symbol.file, *header, 'class_header', symbol.parent)
    imports = []
    for symbol in selected:
        uses = {u['name'] for u in parsed[symbol.file]['identifier_uses'] if symbol.start_line <= u['line'] <= symbol.end_line}
        imports.extend(r for r in parsed[symbol.file]['esm_imports'] if r['alias'] in uses)
    omitted_imports = 0
    for ref in imports:
        if remaining:
            add(ref['file'], ref['start_line'], ref['end_line'], 'import_binding')
        else:
            omitted_imports += 1
    return {'schema_version': 1, 'target': asdict(index.symbols[sid]), 'blocks': blocks,
            'max_lines': max_lines, 'used_lines': max_lines - remaining,
            'budget_exhausted': remaining == 0, 'truncated': any(b['truncated'] for b in blocks),
            'omitted_imports': omitted_imports, 'call_evidence': [],
            'scope': 'A3 source context; ordinary call resolution and impact not supported'}


def experiment_map(index, parsed, analysis, fingerprint, out, sid, depth):
    from repo_doctor.repo_map import build_map, project_view
    from repo_doctor.map_render import render_html, render_svg
    data = build_map(index, symbol=sid, depth=depth)
    data['repository']['source_fingerprint'] = fingerprint
    data['coverage'].update(python_files=0, unresolved_calls=sum(len(p['calls']) for p in parsed.values()), scope=analysis['scope'])
    data['analysis'] = analysis
    for node in data['nodes']:
        if node['kind'] == 'file':
            node.update(python=False, analyzed=node['file'] in parsed, language=path_language(node['file']))
    # Temporary experiment adapter; formal map/viewer remain unchanged until B3.
    projection = copy.deepcopy(data)
    for node in projection['nodes']:
        if node['kind'] == 'file':
            node['python'] = node['analyzed']
    data['views'] = {mode: project_view(projection, mode, symbol=sid, depth=depth) for mode in ('structure', 'relations')}
    out.mkdir(parents=True, exist_ok=False)
    (out / 'map.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    html = render_html(data).replace('node.python', '(node.analyzed ?? node.python)').replace('n.python', '(n.analyzed ?? n.python)')
    (out / 'map.html').write_text(html, encoding='utf-8')
    for mode, view in data['views'].items():
        (out / (mode + '.svg')).write_text(render_svg(data, view), encoding='utf-8')
    return {'schema_version': 1, 'output': str(out), 'nodes': len(data['nodes']), 'edges': len(data['edges']), 'analysis': analysis}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('overview', 'symbols', 'context', 'impact', 'map'))
    parser.add_argument('root', type=Path)
    parser.add_argument('symbol', nargs='?')
    parser.add_argument('--languages', required=True)
    parser.add_argument('--query', default='')
    parser.add_argument('--include-symbol', action='append', default=[])
    parser.add_argument('--max-lines', type=int, default=120)
    parser.add_argument('--depth', type=int, default=2)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        languages = tuple(args.languages.split(','))
        if not languages or any(l not in ('javascript', 'typescript') for l in languages):
            raise ValueError('Only explicit javascript/typescript languages supported by spike')
        index, parsed, analysis, fingerprint = build_spike(args.root, languages)
        if args.command == 'overview':
            result = {'schema_version': 1, 'root': str(index.root), 'scan_mode': index.scan_mode,
                      'source_fingerprint': fingerprint, 'stats': {'python_files': 0, 'symbols': len(index.symbols),
                      'resolved_calls': 0, 'unresolved_calls': sum(len(p['calls']) for p in parsed.values()),
                      'parse_errors': len(index.parse_errors), 'ambiguous_symbols': len(index.ambiguous_symbols)},
                      'sample_symbols': [asdict(s) for s in list(index.symbols.values())[:20]],
                      'parse_errors': [asdict(e) for e in index.parse_errors]}
        elif args.command == 'symbols':
            result = {'schema_version': 1, 'query': args.query, 'matches': [asdict(s) for s in index.symbols.values() if args.query.lower() in s.id.lower()]}
        elif args.command == 'context':
            result = context(index, parsed, args.symbol, args.include_symbol, args.max_lines)
        elif args.command == 'impact':
            if args.symbol not in index.symbols:
                raise ValueError('Unknown or ambiguous symbol')
            result = {'schema_version': 1, 'target': asdict(index.symbols[args.symbol]),
                      'affected_symbols': [], 'depth': args.depth, 'status': 'not-supported',
                      'scope': 'A3 ordinary call/impact resolution is not supported; empty result does not prove no impact'}
        else:
            if args.out is None:
                raise ValueError('map requires --out')
            result = experiment_map(index, parsed, analysis, fingerprint, args.out, args.symbol, args.depth)
        result['analysis'] = analysis
        print(json.dumps(result, ensure_ascii=False, default=sorted))
        return 0
    except (ValueError, OSError, ImportError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
