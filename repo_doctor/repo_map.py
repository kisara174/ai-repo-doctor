"""Deterministic structure projection of the existing static repository index."""

import hashlib
import json
from collections import deque
from pathlib import Path, PurePosixPath

from .case import _revision, source_fingerprint
from .model import RepoIndex
from .scanner import discover_files
from .map_render import render_html, render_svg
from .languages import analysis_metadata


LAYOUT = {'node_width': 260, 'node_height': 54, 'column_gap': 320,
          'row_gap': 90, 'margin': 30, 'header': 120, 'columns': 3, 'indent': 26}
KINDS = ['import', 'call', 'reexport', 'command_registration']
COLORS = {'contains': '#94a3b8', 'import': '#64748b', 'call': '#2563eb',
          'reexport': '#9333ea', 'command_registration': '#c2410c'}


def build_map(index: RepoIndex, *, symbol: str | None = None, depth: int = 1) -> dict:
    if depth not in (1, 2):
        raise ValueError('map depth must be 1 or 2')
    if symbol is not None and symbol not in index.symbols:
        raise ValueError(f'Unknown symbol: {symbol}')
    fingerprint = source_fingerprint(index)
    paths, mode = discover_files(index.root)
    nodes = {'dir:.': {'id': 'dir:.', 'kind': 'directory', 'label': index.root.name,
                       'file': '.', 'parent': None, 'is_test': False}}
    records = {item.path: item for item in index.files}
    for path in paths:
        parts = PurePosixPath(path).parts
        parent = 'dir:.'
        for end in range(1, len(parts)):
            folder = '/'.join(parts[:end])
            node_id = f'dir:{folder}'
            nodes.setdefault(node_id, {'id': node_id, 'kind': 'directory', 'label': parts[end - 1],
                                      'file': folder, 'parent': parent, 'is_test': False})
            parent = node_id
        record = records.get(path)
        nodes[f'file:{path}'] = {'id': f'file:{path}', 'kind': 'file', 'label': parts[-1],
                                'file': path, 'parent': parent, 'is_test': bool(record and record.is_test),
                                'language': index.file_languages.get(path), 'analyzed': record is not None,
                                'python': record is not None and index.file_languages.get(path, 'python') == 'python'}
    for item in sorted(index.symbols.values(), key=lambda value: value.id):
        nodes[f'symbol:{item.id}'] = {
            'id': f'symbol:{item.id}', 'kind': item.kind, 'label': item.qualname,
            'file': item.file, 'symbol': item.id, 'start_line': item.start_line, 'end_line': item.end_line,
            'parent': f'symbol:{item.parent}' if item.parent in index.symbols else f'file:{item.file}',
            'is_test': records[item.file].is_test,
        }
    grouped = {}

    def add(kind, source, target, evidence=None):
        if source not in nodes or target not in nodes:
            return
        key = (kind, source, target)
        edge = grouped.setdefault(key, {'id': hashlib.sha256(json.dumps(key).encode()).hexdigest()[:20],
                                        'kind': kind, 'source': source, 'target': target, 'evidence': []})
        if evidence is not None and evidence not in edge['evidence']:
            edge['evidence'].append(evidence)

    for node in nodes.values():
        if node['parent']:
            add('contains', node['parent'], node['id'])
    for edge in index.import_edges:
        add('import', f'file:{edge.source}', f'file:{edge.target}', {'file': edge.source, 'line': edge.line})
    for edge in index.call_edges:
        add('call', f'symbol:{edge.caller}', f'symbol:{edge.callee}',
            {'file': index.symbols[edge.caller].file, 'line': edge.line})
    for edge in index.semantic_edges:
        source = f'symbol:{edge.source_symbol}' if edge.source_symbol else f'file:{edge.source_file}'
        add(edge.kind, source, f'symbol:{edge.target_symbol}', {'file': edge.evidence_file, 'line': edge.line})
    edges = sorted(grouped.values(), key=lambda edge: (edge['kind'], edge['source'], edge['target']))
    file_edges = {}
    for edge in edges:
        if edge['kind'] == 'contains':
            continue
        source = f"file:{nodes[edge['source']]['file']}"
        target = f"file:{nodes[edge['target']]['file']}"
        if source == target:
            continue
        key = (edge['kind'], source, target)
        projected = file_edges.setdefault(key, {**edge, 'id': 'file-' + hashlib.sha256(json.dumps(key).encode()).hexdigest()[:20],
                                                'source': source, 'target': target, 'evidence': []})
        for evidence in edge['evidence']:
            if evidence not in projected['evidence']:
                projected['evidence'].append(evidence)
    data = {
        'schema_version': 1, 'repository': {'name': index.root.name, 'revision': _revision(index.root),
                                           'source_fingerprint': fingerprint, 'scan_mode': mode},
        'coverage': {'python_files': sum(index.file_languages.get(row.path, 'python') == 'python' for row in index.files), 'parse_errors': len(index.parse_errors),
                     'resolved_calls': len(index.call_edges), 'unresolved_calls': len(index.calls) - len(index.call_edges),
                     'ambiguous_symbols': len(index.ambiguous_symbols), 'scope': 'static selected source languages; no runtime completeness'},
        'nodes': sorted(nodes.values(), key=lambda node: node['id']), 'edges': edges,
        'file_edges': sorted(file_edges.values(), key=lambda edge: (edge['kind'], edge['source'], edge['target'])),
        'layout': LAYOUT, 'limits': {'nodes': 200, 'edges': 500}, 'colors': COLORS,
        'initial': {'symbol': symbol, 'depth': depth},
        'analysis': analysis_metadata(index),
    }
    data['views'] = {mode: project_view(data, mode, symbol=symbol, depth=depth) for mode in ('structure', 'relations')}
    if source_fingerprint(index) != fingerprint:
        raise ValueError('source changed during map generation; rerun map')
    return data


def project_view(data: dict, mode: str, *, symbol: str | None = None, depth: int = 1,
                 include_tests: bool = False, kinds: list[str] | None = None) -> dict:
    nodes = data['nodes']
    edges = data['edges']
    selected = []
    if mode == 'structure':
        selected = [node for node in nodes if node['id'] == 'dir:.' or node['parent'] == 'dir:.']
        edges = [edge for edge in edges if edge['kind'] == 'contains']
        selected.sort(key=lambda node: ('' if node['id'] == 'dir:.' else node['file'], node['kind']))
    elif symbol:
        target = f'symbol:{symbol}'
        edges = [edge for edge in edges if edge['kind'] != 'contains']
        seen = {target}
        queue = deque([(target, 0)])
        while queue:
            current, distance = queue.popleft()
            if distance >= depth:
                continue
            for edge in edges:
                for neighbor in ([edge['target']] if edge['source'] == current else
                                 [edge['source']] if edge['target'] == current else []):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        queue.append((neighbor, distance + 1))
        selected = [node for node in nodes if node['id'] in seen]
    else:
        selected = [node for node in nodes if node['kind'] == 'file' and node.get('analyzed', node.get('python', False))]
        edges = data['file_edges']
    selected = [node for node in selected if include_tests or not node['is_test']
                or (symbol is not None and node.get('symbol') == symbol)]
    if symbol and mode == 'relations':
        selected.sort(key=lambda node: (node.get('symbol') != symbol, node['id']))
    selected = selected[:data['limits']['nodes']]
    ids = {node['id'] for node in selected}
    allowed = set(KINDS if kinds is None else kinds) | {'contains'}
    visible_edges = [edge for edge in edges if edge['source'] in ids and edge['target'] in ids and edge['kind'] in allowed]
    visible_edges = visible_edges[:data['limits']['edges']]
    view = {'mode': mode, 'nodes': selected, 'edges': visible_edges,
            'hidden_nodes': len(nodes) - len(selected), 'hidden_edges': len(edges) - len(visible_edges)}
    return position_view(data, view)


def position_view(data: dict, view: dict) -> dict:
    layout = data['layout']
    positioned = []
    lookup = {node['id']: node for node in data['nodes']}
    for row, node in enumerate(view['nodes']):
        if view['mode'] == 'structure':
            level, parent = 0, node.get('parent')
            while parent in lookup:
                level += 1
                parent = lookup[parent].get('parent')
            x = layout['margin'] + level * layout['indent']
            y = layout['header'] + row * layout['row_gap']
        else:
            x = layout['margin'] + (row % layout['columns']) * layout['column_gap']
            y = layout['header'] + (row // layout['columns']) * layout['row_gap']
        positioned.append({**node, 'x': x, 'y': y})
    return {**view, 'nodes': positioned,
            'width': max(960, max((node['x'] + layout['node_width'] + 30 for node in positioned), default=960)),
            'height': max(300, max((node['y'] + layout['node_height'] + 30 for node in positioned), default=300))}


def write_map(index: RepoIndex, destination: Path, *, symbol: str | None = None, depth: int = 1) -> dict:
    if destination.exists() or destination.is_symlink():
        raise ValueError('Map directory already exists; choose a new output directory')
    data = build_map(index, symbol=symbol, depth=depth)
    artifacts = {'map.json': json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                 'map.html': render_html(data),
                 'structure.svg': render_svg(data, data['views']['structure']),
                 'relations.svg': render_svg(data, data['views']['relations'])}
    destination.mkdir(parents=True)
    for name, content in artifacts.items():
        (destination / name).write_text(content, encoding='utf-8')
    return {'schema_version': 1, 'directory': str(destination.resolve()), 'map_json': str((destination / 'map.json').resolve()),
            'html': str((destination / 'map.html').resolve()),
            'structure_svg': str((destination / 'structure.svg').resolve()),
            'relations_svg': str((destination / 'relations.svg').resolve()),
            'coverage': data['coverage'], 'analysis': data['analysis']}
