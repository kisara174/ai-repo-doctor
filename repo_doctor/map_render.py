"""Self-contained SVG and HTML from the shared repository map views."""

import json
import xml.etree.ElementTree as ET
from importlib.resources import files


SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)


def render_svg(data: dict, view: dict) -> str:
    def element(parent, name, attributes=None, text=None):
        node = ET.SubElement(parent, f'{{{SVG}}}{name}', {key: str(value) for key, value in (attributes or {}).items()})
        if text is not None:
            node.text = str(text)
        return node

    root = ET.Element(f'{{{SVG}}}svg', {'viewBox': f"0 0 {view['width']} {view['height']}",
                                       'width': str(view['width']), 'height': str(view['height']),
                                       'role': 'img', 'aria-label': '仓库结构关系图'})
    element(root, 'title', text=f"{data['repository']['name']} · 仓库结构关系图")
    element(root, 'rect', {'width': '100%', 'height': '100%', 'fill': '#f8fafc'})
    defs = element(root, 'defs')
    for kind, color in data['colors'].items():
        marker = element(defs, 'marker', {'id': f'arrow-{kind}', 'viewBox': '0 0 10 10',
                                         'refX': 9, 'refY': 5, 'markerWidth': 6, 'markerHeight': 6, 'orient': 'auto-start-reverse'})
        element(marker, 'path', {'d': 'M 0 0 L 10 5 L 0 10 z', 'fill': color})
    element(root, 'text', {'x': 30, 'y': 32, 'font-family': 'system-ui, sans-serif', 'font-size': 20, 'fill': '#0f172a'},
            f"{data['repository']['name']} · {'文件结构' if view['mode'] == 'structure' else '静态关系'}")
    element(root, 'text', {'x': 30, 'y': 58, 'font-family': 'system-ui, sans-serif', 'font-size': 12, 'fill': '#475569'},
            f"静态分析 · 未解析调用 {data['coverage']['unresolved_calls']} · 解析失败 {data['coverage']['parse_errors']} · 未显示节点 {view['hidden_nodes']} / 连线 {view['hidden_edges']}")
    element(root, 'text', {'x': 30, 'y': 80, 'font-family': 'system-ui, sans-serif', 'font-size': 12, 'fill': '#64748b'},
            f"源码 {data['repository']['source_fingerprint'][:16]} · 修订 {(data['repository']['revision'] or '无 Git 修订')[:16]} · 箭头：调用者/导入者 → 目标")
    labels = {'contains': '包含', 'import': '导入', 'call': '调用', 'reexport': '重导出', 'command_registration': '注册'}
    for column, (kind, color) in enumerate(data['colors'].items()):
        element(root, 'text', {'x': 30 + column * 140, 'y': 102, 'font-family': 'system-ui, sans-serif', 'font-size': 12, 'fill': color},
                f"● {labels.get(kind, kind)}")
    layout = data['layout']
    lookup = {node['id']: node for node in view['nodes']}
    for edge in view['edges']:
        source, target = lookup[edge['source']], lookup[edge['target']]
        width, height = layout['node_width'], layout['node_height']
        if target['x'] > source['x']:
            x1, y1 = source['x'] + width, source['y'] + height / 2
            x2, y2 = target['x'], target['y'] + height / 2
        else:
            x1, y1 = source['x'] + width / 2, source['y'] + height
            x2, y2 = target['x'] + width / 2, target['y']
        geometry = f'M {x1} {y1} C {x1 + 35} {y1}, {x2 - 35} {y2}, {x2} {y2}'
        if edge['kind'] == 'contains':
            geometry = f"M {source['x'] + 12} {source['y'] + height} V {target['y'] + height / 2} H {target['x']}"
        path = element(root, 'path', {'d': geometry,
                                     'fill': 'none', 'stroke': data['colors'][edge['kind']], 'stroke-width': 1.5,
                                     'opacity': 0.6, 'marker-end': f"url(#arrow-{edge['kind']})", 'data-edge-id': edge['id']})
        element(path, 'title', text=f"{labels.get(edge['kind'], edge['kind'])}: {source['label']} → {target['label']}")
    for node in view['nodes']:
        group = element(root, 'g', {'data-node-id': node['id'], 'transform': f"translate({node['x']},{node['y']})"})
        element(group, 'title', text=f"{node['label']} · {node['file']}")
        element(group, 'rect', {'width': layout['node_width'], 'height': layout['node_height'], 'rx': 8,
                                'fill': '#eff6ff' if node['kind'] == 'directory' else '#ffffff', 'stroke': '#cbd5e1'})
        label = node['label'] if len(node['label']) <= 32 else node['label'][:31] + '…'
        element(group, 'text', {'x': 12, 'y': 22, 'font-family': 'system-ui, sans-serif', 'font-size': 13, 'fill': '#0f172a'}, label)
        detail = node['file'] if len(node['file']) <= 40 else '…' + node['file'][-39:]
        element(group, 'text', {'x': 12, 'y': 42, 'font-family': 'system-ui, sans-serif', 'font-size': 10, 'fill': '#64748b'}, detail)
    return ET.tostring(root, encoding='unicode') + '\n'


def render_html(data: dict) -> str:
    resources = files('repo_doctor').joinpath('resources/map')
    page = resources.joinpath('viewer.html').read_text(encoding='utf-8')
    style = resources.joinpath('viewer.css').read_text(encoding='utf-8')
    script = resources.joinpath('viewer.js').read_text(encoding='utf-8')
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return page.replace('@@STYLE@@', style).replace('@@SCRIPT@@', script).replace('@@DATA@@', payload)
