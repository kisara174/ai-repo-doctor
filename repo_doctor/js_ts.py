"""Optional JS/TS syntax backend; never imports or executes target code."""
from bisect import bisect_right
from collections import Counter
from functools import lru_cache
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path, PurePosixPath

from .languages import language_for_path
from .model import (AnalysisLimit, CallSite, ESMExportRef, ESMImportRef, FileRecord,
                    IdentifierUse, JSParsedFile, OverloadSignature, ParsedFile, ParseError, Symbol)
from .source import read_source

EXTRA_HELP = "JS/TS backend unavailable or incompatible; install ai-repo-doctor[js]"


@lru_cache(maxsize=2)
def _parser(language):
    if language not in ("javascript", "typescript"):
        raise ValueError("JS/TS parser requires javascript or typescript")
    try:
        for name, pinned in (("tree-sitter", "0.26.0"), ("tree-sitter-javascript", "0.25.0"),
                             ("tree-sitter-typescript", "0.23.2")):
            if version(name) != pinned:
                raise ValueError(EXTRA_HELP)
        from tree_sitter import Language, Parser
        if language == "javascript":
            import tree_sitter_javascript as grammar
            capsule = grammar.language()
        else:
            import tree_sitter_typescript as grammar
            capsule = grammar.language_typescript()
        return Parser(Language(capsule))
    except (ImportError, PackageNotFoundError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError(EXTRA_HELP) from exc


def parse_tree(source, language):
    raw = source.encode("utf-8")
    return raw, _parser(language).parse(raw)


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
                            if item.type != "import_specifier":
                                continue
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
                    if item.type != "export_specifier":
                        continue
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
            limit(node, 'calls-not-supported', 'Ordinary JS/TS call targets are not resolved at this stage')
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


def parse_js_ts_file(root: Path, relative_path: str, *,
                     root_identity: tuple[int, int] | None = None) -> JSParsedFile:
    language = language_for_path(relative_path)
    if language not in ("javascript", "typescript"):
        raise ValueError("Unsupported JS/TS implementation path: " + relative_path)
    _parser(language)  # dependency errors are input errors, never file parse errors
    parts = PurePosixPath(relative_path).parts
    is_test = ("test" in parts or "tests" in parts or
               PurePosixPath(relative_path).name.startswith("test_"))
    try:
        source = read_source(root, relative_path, root_identity, language=language)
    except (UnicodeError, SyntaxError) as exc:
        parsed = ParsedFile(FileRecord(relative_path, 0, 0, is_test), [], [], [],
                            error=ParseError(relative_path, 1, "Invalid UTF-8 source: " + str(exc)))
        return JSParsedFile(parsed, [], [], [], set(), {}, [])
    lines = source.splitlines()
    data = extract(source, file=relative_path, language=language)
    symbols = [Symbol(**{**row, "local_bindings": frozenset(row["local_bindings"]),
                         "overloads": tuple(OverloadSignature(**sig) for sig in row["overloads"])})
               for row in data["symbols"]]
    # Ownerless module/callback calls cannot masquerade as a named-symbol CallSite.
    calls = [CallSite(**row) for row in data["calls"] if row["caller"] is not None]
    parsed = ParsedFile(FileRecord(relative_path, len(lines), sum(bool(line.strip()) for line in lines), is_test),
                        symbols, [], calls, error=ParseError(**data["error"]) if data["error"] else None)
    return JSParsedFile(parsed, [ESMImportRef(**row) for row in data["esm_imports"]],
                        [ESMExportRef(**row) for row in data["esm_exports"]],
                        [IdentifierUse(**row) for row in data["identifier_uses"]],
                        set(data["unsafe_bindings"]), data["class_header_spans"],
                        [AnalysisLimit(**row) for row in data["limits"]])
