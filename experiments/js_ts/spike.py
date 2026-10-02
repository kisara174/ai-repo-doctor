"""Disposable JS/TS syntax experiment. Never imports or executes target code."""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
from dataclasses import asdict
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat


def parse_tree(source, language):
    from tree_sitter import Language, Parser
    if language == 'javascript':
        import tree_sitter_javascript as grammar
        capsule = grammar.language()
    elif language == 'typescript':
        import tree_sitter_typescript as grammar
        capsule = grammar.language_typescript()
    else:
        raise ValueError('spike supports javascript/typescript only')
    raw = source.encode('utf-8')
    return raw, Parser(Language(capsule)).parse(raw)


def extract(source: str, *, file: str, language: str) -> dict:
    raw, tree = parse_tree(source, language)
    # Point.column crashes the pinned native binding on this Mac. Offsets remain usable.
    line_starts = [0] + [i + 1 for i, byte in enumerate(raw) if byte == 10]

    def span(node):
        start = bisect_right(line_starts, node.start_byte)
        end = bisect_right(line_starts, max(node.start_byte, node.end_byte - 1))
        return start, max(start, end)
    data = {key: [] for key in ('symbols', 'esm_imports', 'esm_exports', 'calls',
                                'identifier_uses', 'limits')}
    data.update(unsafe_bindings=[], class_header_spans={}, error=None)

    def text(node):
        return raw[node.start_byte:node.end_byte].decode('utf-8') if node else ''

    def descendants(node):
        yield node
        for child in node.named_children:
            yield from descendants(child)

    errors = [n for n in descendants(tree.root_node) if n.type == 'ERROR' or n.is_missing]
    if errors:
        first = min(errors, key=lambda n: (n.start_byte, n.end_byte))
        data['error'] = {'file': file, 'line': span(first)[0], 'message': 'Tree-sitter ERROR/missing; whole file excluded'}
        return data

    def limit(node, reason, message):
        item = {'file': file, 'line': span(node)[0], 'reason': reason, 'message': message}
        if item not in data['limits']:
            data['limits'].append(item)

    def binding_names(node):
        if node is None:
            return set()
        if node.type in ('identifier', 'shorthand_property_identifier_pattern'):
            return {text(node)}
        if node.type in ('required_parameter', 'optional_parameter', 'pair_pattern', 'assignment_pattern', 'object_assignment_pattern'):
            return binding_names(node.child_by_field_name('pattern') or node.child_by_field_name('value')
                                 or node.child_by_field_name('left'))
        if node.type in ('formal_parameters', 'object_pattern', 'array_pattern', 'rest_pattern'):
            result = set()
            for child in node.named_children:
                result.update(binding_names(child))
            return result
        if node.type not in ('member_expression', 'subscript_expression', 'comment'):
            unsafe.add('*')
            limit(node, 'unknown-binding', 'Unrecognized binding blocks ordinary call resolution for this file')
        return set()

    signatures = {}
    unsafe = set()

    def symbol(node, name, kind, parent, span_node=None):
        qualname = name if parent is None else parent.split('::', 1)[1] + '.' + name
        sid = file + '::' + qualname
        start, end = span(span_node or node)
        local = binding_names(node.child_by_field_name('parameters') or node.child_by_field_name('parameter'))
        body = node.child_by_field_name('body')
        if body:
            for inner in descendants(body):
                if inner.type in ('variable_declarator', 'catch_clause'):
                    local.update(binding_names(inner.child_by_field_name('name') or inner.child_by_field_name('parameter')))
                elif inner.type in ('function_declaration', 'class_declaration'):
                    local.update(binding_names(inner.child_by_field_name('name')))
        item = {'id': sid, 'file': file, 'name': name, 'qualname': qualname,
                'kind': kind, 'start_line': start, 'end_line': end, 'parent': parent,
                'local_bindings': sorted(local), 'is_async': any(c.type == 'async' for c in node.children),
                'overloads': []}
        data['symbols'].append(item)
        if kind == 'class' and body:
            data['class_header_spans'][sid] = (span(node)[0], span(body)[0])
        return sid

    def esm(node):
        start, end = span(node)
        source_node = node.child_by_field_name('source')
        specifier = text(source_node)[1:-1] if source_node else None
        top_type = any(c.type == 'type' for c in node.children)
        if specifier is not None and ('\\' in specifier or '${' in specifier):
            limit(node, 'escaped-specifier', 'Escaped module specifier is retained but not resolved')
        if node.type == 'import_statement':
            clause = next((c for c in node.named_children if c.type == 'import_clause'), None)
            rows = []
            if clause:
                for child in clause.named_children:
                    if child.type == 'identifier':
                        rows.append(('default', text(child), top_type))
                    elif child.type == 'namespace_import':
                        rows.append(('*', text(child.named_children[-1]), top_type))
                    elif child.type == 'named_imports':
                        for item in child.named_children:
                            name = item.child_by_field_name('name')
                            alias = item.child_by_field_name('alias') or name
                            rows.append((text(name), text(alias), top_type or any(c.type == 'type' for c in item.children)))
            else:
                rows.append((None, None, False))
            for imported, alias, type_only in rows:
                data['esm_imports'].append({'file': file, 'specifier': specifier,
                    'imported': imported, 'alias': alias, 'start_line': start, 'end_line': end,
                    'type_only': type_only, 'resolved_file': None, 'resolution_kind': None})
        else:
            clause = next((c for c in node.named_children if c.type == 'export_clause'), None)
            if clause:
                for item in clause.named_children:
                    name = text(item.child_by_field_name('name'))
                    exported = text(item.child_by_field_name('alias')) or name
                    data['esm_exports'].append({'file': file, 'exported': exported,
                        'local_name': None if specifier else name, 'specifier': specifier,
                        'imported': name if specifier else None, 'start_line': start, 'end_line': end,
                        'type_only': top_type or any(c.type == 'type' for c in item.children)})
            elif specifier:
                data['esm_exports'].append({'file': file, 'exported': '*', 'local_name': None,
                    'specifier': specifier, 'imported': '*', 'start_line': start, 'end_line': end,
                    'type_only': top_type})
            else:
                decl = node.child_by_field_name('declaration') or node.child_by_field_name('value')
                default = any(c.type == 'default' for c in node.children)
                names = []
                if decl:
                    if decl.type == 'lexical_declaration':
                        names = [text(n.child_by_field_name('name')) for n in decl.named_children
                                 if n.type == 'variable_declarator' and n.child_by_field_name('name').type == 'identifier']
                    elif decl.type in ('function_declaration', 'generator_function_declaration', 'function_expression', 'class_declaration', 'function_signature'):
                        names = [text(decl.child_by_field_name('name')) or '<default>']
                    elif default and decl.type == 'identifier':
                        names = [text(decl)]
                for name in names:
                    data['esm_exports'].append({'file': file, 'exported': 'default' if default else name,
                        'local_name': name, 'specifier': None, 'imported': None, 'start_line': start,
                        'end_line': end, 'type_only': top_type})

    def walk(node, owner=None, parent=None):
        if node.type in ('comment', 'string', 'type_annotation', 'type_alias_declaration', 'interface_declaration'):
            return
        if node.type in ('import_statement', 'export_statement'):
            esm(node)
            if node.type == 'import_statement':
                return
        if node.type == 'function_signature':
            name = text(node.child_by_field_name('name'))
            sid = file + '::' + ((parent.split('::', 1)[1] + '.') if parent else '') + name
            start, end = span(node)
            signatures.setdefault(sid, []).append({'start_line': start, 'end_line': end, 'signature': text(node)})
            return
        if node.type in ('function_declaration', 'generator_function_declaration', 'class_declaration', 'method_definition'):
            name = text(node.child_by_field_name('name'))
            if node.type == 'method_definition' and node.child_by_field_name('name').type not in ('property_identifier', 'identifier'):
                limit(node, 'computed-method', 'Computed method name is unsupported')
                return
            if name:
                kind = 'class' if node.type == 'class_declaration' else 'method' if node.type == 'method_definition' else 'function'
                sid = symbol(node, name, kind, parent)
                if parent:
                    limit(node, 'nested-scope', 'Nested or class symbols are searchable; calls are not resolved')
                for child in node.named_children:
                    if child == node.child_by_field_name('body'):
                        walk(child, None if kind == 'class' else sid, sid)
                return
        if node.type == 'variable_declarator':
            name_node, value = node.child_by_field_name('name'), node.child_by_field_name('value')
            const = node.parent and node.parent.type == 'lexical_declaration' and any(c.type == 'const' for c in node.parent.children)
            if const and name_node.type == 'identifier' and value and value.type in ('arrow_function', 'function_expression', 'generator_function'):
                sid = symbol(value, text(name_node), 'function', parent, node.parent)
                body = value.child_by_field_name('body')
                if body:
                    walk(body, sid, sid)
                return
        if node.type in ('arrow_function', 'function_expression', 'generator_function'):
            if node.parent and node.parent.type == 'export_statement' and any(c.type == 'default' for c in node.parent.children):
                name = text(node.child_by_field_name('name')) or '<default>'
                sid = symbol(node, name, 'function', parent)
                body = node.child_by_field_name('body')
                if body:
                    walk(body, sid, sid)
            else:
                limit(node, 'anonymous-callback', 'Anonymous callback calls have no enclosing named caller')
                for child in node.named_children:
                    walk(child, None, parent)
            return
        if node.type in ('assignment_expression', 'augmented_assignment_expression', 'update_expression'):
            target = node.child_by_field_name('left') or node.child_by_field_name('argument')
            names = binding_names(target)
            unsafe.update(names)
            if not names and target and target.type not in ('member_expression', 'subscript_expression'):
                unsafe.add('*')
                limit(node, 'unknown-binding', 'Unrecognized assignment blocks call resolution for this file')
        if node.type == 'identifier':
            data['identifier_uses'].append({'file': file, 'name': text(node), 'line': span(node)[0]})
        if node.type == 'call_expression':
            target = node.child_by_field_name('function')
            name = text(target)
            receiver = None if target.type == 'identifier' else name
            data['calls'].append({'file': file, 'caller': owner, 'expression': name, 'name': name,
                                  'receiver': receiver, 'line': span(node)[0],
                                  'column': node.start_byte - line_starts[bisect_right(line_starts, node.start_byte) - 1]})
            limit(node, 'calls-not-supported', 'A3 prototype records call points without resolving targets')
        for child in node.named_children:
            walk(child, owner, parent)

    walk(tree.root_node)
    for item in data['symbols']:
        item['overloads'] = signatures.pop(item['id'], [])
    for sid, entries in signatures.items():
        data['limits'].append({'file': file, 'line': entries[0]['start_line'],
                              'reason': 'declaration-only', 'message': sid + ' has no implementation'})
    counts = Counter(s['id'] for s in data['symbols'])
    for sid, count in counts.items():
        if count > 1:
            data['limits'].append({'file': file, 'line': None, 'reason': 'ambiguous-symbol', 'message': sid})
    data['unsafe_bindings'] = sorted(unsafe)
    return data


def source_text(root, path, identity):
    """Temporary UTF-8 adapter using the existing checked FD open primitives."""
    from repo_doctor.source import _open_no_follow, _open_checked_fallback
    relative = PurePosixPath(path)
    if relative.is_absolute() or not relative.parts or '..' in relative.parts or '\\' in path:
        raise ValueError('Unsafe source path')
    opener = _open_no_follow if os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY') else _open_checked_fallback
    descriptor = opener(root, relative.parts, identity)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Source is not a regular file')
        return stream.read().decode('utf-8-sig')


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
