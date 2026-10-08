"""Retrieve bounded source context and reverse dependency impact."""

import ast
from collections import defaultdict, deque
from dataclasses import asdict

from .model import CallEdge, RepoIndex, SemanticEdge, Symbol
from .limits import AnalysisLimitError
from .source import read_source
from .languages import analysis_metadata


def _call_edge_data(index: RepoIndex, edge: CallEdge) -> dict:
    data = {
        "caller": edge.caller,
        "callee": edge.callee,
        "file": index.symbols[edge.caller].file,
        "line": edge.line,
        "via_reexports": [asdict(hop) for hop in edge.via_reexports],
    }
    ref = index.js_call_imports.get((edge.caller, edge.callee, edge.line))
    if ref is not None:
        data['via_esm_import'] = asdict(ref)
    return data


def _require_symbol(index: RepoIndex, symbol_id: str) -> Symbol:
    if symbol_id in index.ambiguous_symbols:
        raise ValueError(f"Ambiguous symbol: {symbol_id}")
    try:
        return index.symbols[symbol_id]
    except KeyError as exc:
        raise ValueError(f"Unknown symbol: {symbol_id}") from exc


def _read_lines(index: RepoIndex, path: str) -> list[str]:
    return read_source(index.root, path, index.root_identity,
                       language=index.file_languages.get(path, "python"), budget=index.budget).splitlines()


def _semantic_edge_data(edge: SemanticEdge, symbol_id: str) -> dict:
    data = asdict(edge)
    data["direction"] = "outgoing" if edge.source_symbol == symbol_id else "incoming"
    return data


def _class_header_span(source: list[str], symbol: Symbol) -> tuple[int, int] | None:
    try:
        module = ast.parse("\n".join(source))
    except (SyntaxError, ValueError):
        return None
    matches = [
        node for node in ast.walk(module)
        if isinstance(node, ast.ClassDef)
        and node.name == symbol.name
        and node.end_lineno == symbol.end_line
        and symbol.start_line <= node.lineno <= symbol.end_line
    ]
    if len(matches) != 1:
        return None
    node = matches[0]
    first_body = node.body[0]
    first_body_line = first_body.lineno
    for decorator in getattr(first_body, "decorator_list", ()):
        first_body_line = min(first_body_line, decorator.lineno)
    end = max(node.lineno, first_body_line - 1)
    while end > node.lineno and (not source[end - 1].strip() or source[end - 1].lstrip().startswith("#")):
        end -= 1
    return node.lineno, min(end, symbol.end_line)


def build_context(
    index: RepoIndex,
    symbol_id: str,
    max_lines: int = 120,
    *,
    include_symbols: tuple[str, ...] = (),
) -> dict:
    """Return target-first selected and graph context within a source-line budget."""
    target = _require_symbol(index, symbol_id)
    if max_lines < 1:
        raise ValueError("max_lines must be at least 1")

    candidates: list[tuple[str, str]] = [(target.id, "target")]
    seen = {target.id}
    source_cache: dict[str, list[str]] = {}

    def source_lines(path: str) -> list[str]:
        if path not in source_cache:
            source_cache[path] = _read_lines(index, path)
        return source_cache[path]

    candidate_spans: dict[str, tuple[int, int]] = {}
    if target.kind == "method" and target.parent not in index.ambiguous_symbols:
        candidate_owner = index.symbols.get(target.parent or "")
        if candidate_owner is not None and candidate_owner.kind == "class":
            header_span = (index.class_header_spans.get(candidate_owner.id)
                           if index.file_languages.get(candidate_owner.file, "python") != "python"
                           else _class_header_span(source_lines(candidate_owner.file), candidate_owner))
            if header_span is not None:
                seen.add(candidate_owner.id)
                candidates.append((candidate_owner.id, "owner_class"))
                candidate_spans[candidate_owner.id] = header_span

    for requested_id in include_symbols:
        requested = _require_symbol(index, requested_id)
        if requested.id in candidate_spans:
            del candidate_spans[requested.id]
            for position, (candidate_id, _relation) in enumerate(candidates):
                if candidate_id == requested.id:
                    candidates[position] = (requested.id, "user_selected")
                    break
        elif requested.id not in seen:
            seen.add(requested.id)
            candidates.append((requested.id, "user_selected"))

    if index.file_languages.get(target.file, "python") != "python":
        # Explicit includes retain priority over automatically added class headers.
        candidates.sort(key=lambda row: row[1] == "owner_class")

    def add(symbols: set[str], relation: str) -> None:
        for neighbor_id in sorted(
            symbols,
            key=lambda item: (index.symbols[item].file, index.symbols[item].start_line, item),
        ):
            if neighbor_id not in seen:
                seen.add(neighbor_id)
                candidates.append((neighbor_id, relation))

    # Keep local class ancestry beside the target. These definitions can explain
    # inherited behavior such as exception pickling without widening to a full file.
    base_queue = deque([target])
    base_seen = {target.id}
    while base_queue and len(candidates) < max_lines:
        current = base_queue.popleft()
        for expression in current.base_expressions:
            try:
                base = ast.parse(expression, mode="eval").body
            except SyntaxError:
                continue
            if not isinstance(base, ast.Name):
                continue
            base_id = f"{current.file}::{base.id}"
            if base_id in index.ambiguous_symbols:
                continue
            base_symbol = index.symbols.get(base_id)
            if base_symbol is not None and base_symbol.kind != "class":
                continue
            if base_symbol is None:
                matches = {
                    edge.target_symbol
                    for edge in index.semantic_edges
                    if edge.kind == "reexport"
                    and edge.source_file == current.file
                    and edge.exported_name == base.id
                    and edge.target_symbol in index.symbols
                    and index.symbols[edge.target_symbol].kind == "class"
                    and edge.target_symbol not in index.ambiguous_symbols
                }
                base_id = next(iter(matches)) if len(matches) == 1 else ""
                base_symbol = index.symbols.get(base_id)
            if base_symbol is not None and base_id not in base_seen:
                base_seen.add(base_id)
                seen.add(base_id)
                candidates.append((base_id, "base_class"))
                base_queue.append(base_symbol)

    add({edge.callee for edge in index.call_edges if edge.caller == symbol_id}, "callee")
    callers = {edge.caller for edge in index.call_edges if edge.callee == symbol_id}
    test_files = {file.path for file in index.files if file.is_test}
    tests = {item for item in callers if index.symbols[item].file in test_files}
    add(callers - tests, "caller")
    add(tests, "related_test")

    semantic_neighbors = []
    for edge in index.semantic_edges:
        if edge.kind != "command_registration":
            continue
        if edge.source_symbol == symbol_id and edge.target_symbol in index.symbols:
            semantic_neighbors.append((edge.target_symbol, "registered_command"))
        elif edge.target_symbol == symbol_id and edge.source_symbol in index.symbols:
            semantic_neighbors.append((edge.source_symbol, "registered_by"))
    semantic_neighbors.sort(
        key=lambda item: (
            index.symbols[item[0]].file,
            index.symbols[item[0]].start_line,
            item[0],
            item[1],
        )
    )
    for neighbor_id, relation in semantic_neighbors:
        if neighbor_id not in seen:
            seen.add(neighbor_id)
            candidates.append((neighbor_id, relation))

    # Include only module imports whose bound names occur in selected source
    # blocks. This gives the model the local binding needed to interpret a name,
    # while avoiding an unrelated import dump.
    module_names: dict[str, set[str]] = defaultdict(set)
    parsed_modules: dict[str, ast.Module | None] = {}
    for neighbor_id, _relation in candidates:
        symbol = index.symbols[neighbor_id]
        start, end = candidate_spans.get(neighbor_id, (symbol.start_line, symbol.end_line))
        if index.file_languages.get(symbol.file, "python") != "python":
            module_names[symbol.file].update(use.name for use in index.identifier_uses
                                            if use.file == symbol.file and start <= use.line <= end)
            continue
        module = parsed_modules.get(symbol.file)
        if symbol.file not in parsed_modules:
            try:
                module = ast.parse("\n".join(source_lines(symbol.file)))
            except AnalysisLimitError:
                raise
            except (SyntaxError, ValueError):
                module = None
            parsed_modules[symbol.file] = module
        if module is not None:
            for node in ast.walk(module):
                if isinstance(node, ast.Name) and start <= node.lineno <= end:
                    module_names[symbol.file].add(node.id)

    import_rows: dict[tuple[str, int], set[str]] = defaultdict(set)
    for ref in index.imports:
        if (
            ref.owner is None
            and ref.is_unconditional_module_level
            and ref.alias in module_names.get(ref.file, set())
        ):
            import_rows[(ref.file, ref.line)].add(ref.alias)
    import_nodes: dict[tuple[str, int], ast.Import | ast.ImportFrom] = {}
    for file, line in import_rows:
        module = parsed_modules.get(file)
        if module is not None:
            for node in module.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)) and node.lineno == line:
                    import_nodes[(file, line)] = node
                    break

    esm_spans = {}
    for ref in index.esm_imports:
        if ref.alias is not None and ref.alias in module_names.get(ref.file, set()):
            import_rows[(ref.file, ref.start_line)].add(ref.alias)
            esm_spans[(ref.file, ref.start_line)] = ref.end_line

    remaining = max_lines
    blocks: list[dict] = []
    included_symbols = 0
    for neighbor_id, relation in candidates:
        if remaining == 0:
            break
        symbol = index.symbols[neighbor_id]
        source = source_lines(symbol.file)
        start, end = candidate_spans.get(neighbor_id, (symbol.start_line, symbol.end_line))
        end = min(end, len(source))
        selected_end = min(end, start + remaining - 1)
        lines = [{"line": number, "text": source[number - 1]} for number in range(start, selected_end + 1)]
        if not lines:
            continue
        truncated = selected_end < end
        blocks.append(
            {
                "symbol": neighbor_id,
                "relation": relation,
                "file": symbol.file,
                "start_line": start,
                "end_line": selected_end,
                "truncated": truncated,
                "lines": lines,
            }
        )
        remaining -= len(lines)
        included_symbols += 1

    included_imports = 0
    for (file, line), aliases in sorted(import_rows.items()):
        if remaining == 0:
            break
        source = source_lines(file)
        node = import_nodes.get((file, line))
        end = min(esm_spans.get((file, line), getattr(node, "end_lineno", line)), len(source))
        start = line
        selected_end = min(end, start + remaining - 1)
        lines = [
            {"line": number, "text": source[number - 1]}
            for number in range(start, selected_end + 1)
        ]
        if not lines:
            continue
        blocks.append({
            "symbol": f"{file}::<module import {','.join(sorted(aliases))}>",
            "relation": "import_binding",
            "file": file,
            "start_line": start,
            "end_line": selected_end,
            "truncated": selected_end < end,
            "lines": lines,
        })
        remaining -= len(lines)
        included_imports += 1

    direct_edges = [
        _call_edge_data(index, edge)
        for edge in index.call_edges
        if edge.caller == symbol_id or edge.callee == symbol_id
    ]
    semantic_evidence = [
        _semantic_edge_data(edge, symbol_id)
        for edge in index.semantic_edges
        if edge.source_symbol == symbol_id or edge.target_symbol == symbol_id
    ]
    index.budget.checkpoint("context/impact evidence")
    return {
        "schema_version": 2,
        "symbol": symbol_id,
        "max_lines": max_lines,
        "blocks": blocks,
        "call_evidence": direct_edges,
        "semantic_evidence": semantic_evidence,
        "budget_exhausted": (
            any(block["truncated"] for block in blocks)
            or included_symbols < len(candidates)
            or included_imports < len(import_rows)
        ),
        "omitted_symbols": len(candidates) - included_symbols,
        "omitted_imports": len(import_rows) - included_imports,
        **({"analysis": analysis_metadata(index)} if index.analysis_languages != ("python",) else {}),
    }


def build_impact(index: RepoIndex, symbol_id: str, depth: int = 2) -> dict:
    """Follow reverse static call edges; this is not runtime coverage."""
    target = _require_symbol(index, symbol_id)
    if not 1 <= depth <= 10:
        raise ValueError("depth must be from 1 through 10")
    incoming: dict[str, set[str]] = defaultdict(set)
    first_call = {}
    for edge in index.call_edges:
        incoming[edge.callee].add(edge.caller)
        pair = (edge.caller, edge.callee)
        if pair not in first_call or edge.line < first_call[pair].line:
            first_call[pair] = edge
    visited = {symbol_id}
    queue = deque([(symbol_id, 0, [symbol_id])])
    affected = []
    while queue:
        current, distance, path = queue.popleft()
        if distance == depth:
            continue
        for caller in sorted(incoming[current]):
            if caller in visited:
                continue
            visited.add(caller)
            caller_path = [*path, caller]
            call_path_evidence = []
            for callee_id, caller_id in zip(caller_path, caller_path[1:]):
                edge = first_call[(caller_id, callee_id)]
                call_path_evidence.append(_call_edge_data(index, edge))
            affected.append({"symbol": caller, "distance": distance + 1,
                             "path": caller_path, "call_path_evidence": call_path_evidence})
            queue.append((caller, distance + 1, caller_path))
    affected.sort(key=lambda item: (item["distance"], item["symbol"]))
    imports = []
    for edge in index.import_edges:
        if edge.target != target.file or edge.source == target.file:
            continue
        item = {"source": edge.source, "target": edge.target, "line": edge.line}
        association = index.esm_source_associations.get((edge.source, edge.target, edge.line))
        if association is not None:
            item['esm_source_association'] = asdict(association)
        imports.append(item)
    semantic_relations = [
        _semantic_edge_data(edge, symbol_id)
        for edge in index.semantic_edges
        if edge.source_symbol == symbol_id or edge.target_symbol == symbol_id
    ]
    index.budget.checkpoint("context/impact evidence")
    return {
        "schema_version": 2,
        "symbol": symbol_id,
        "depth": depth,
        "affected_symbols": affected,
        "module_importers": sorted({item["source"] for item in imports}),
        "import_evidence": imports,
        "semantic_relations": semantic_relations,
        **({"analysis": analysis_metadata(index)} if index.analysis_languages != ("python",) else {}),
        **({"status": "bounded" if index.js_calls_resolved else "not-supported",
            "scope": "Unique unshadowed direct JS/TS calls only; empty results do not prove no impact"}
           if index.file_languages.get(target.file, "python") != "python" else {}),
    }
