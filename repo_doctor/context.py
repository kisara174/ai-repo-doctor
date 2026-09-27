"""Retrieve bounded source context and reverse dependency impact."""

import ast
from collections import defaultdict, deque
from dataclasses import asdict

from .model import RepoIndex, SemanticEdge, Symbol
from .source import read_source


def _require_symbol(index: RepoIndex, symbol_id: str) -> Symbol:
    if symbol_id in index.ambiguous_symbols:
        raise ValueError(f"Ambiguous symbol: {symbol_id}")
    try:
        return index.symbols[symbol_id]
    except KeyError as exc:
        raise ValueError(f"Unknown symbol: {symbol_id}") from exc


def _read_lines(index: RepoIndex, path: str) -> list[str]:
    return read_source(index.root, path, index.root_identity).splitlines()


def _semantic_edge_data(edge: SemanticEdge, symbol_id: str) -> dict:
    data = asdict(edge)
    data["direction"] = "outgoing" if edge.source_symbol == symbol_id else "incoming"
    return data


def build_context(index: RepoIndex, symbol_id: str, max_lines: int = 120) -> dict:
    """Return target-first one-hop context with a physical source-line budget."""
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
        module = parsed_modules.get(symbol.file)
        if symbol.file not in parsed_modules:
            try:
                module = ast.parse("\n".join(source_lines(symbol.file)))
            except (SyntaxError, ValueError):
                module = None
            parsed_modules[symbol.file] = module
        if module is not None:
            for node in ast.walk(module):
                if isinstance(node, ast.Name) and symbol.start_line <= node.lineno <= symbol.end_line:
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

    remaining = max_lines
    blocks: list[dict] = []
    included_symbols = 0
    for neighbor_id, relation in candidates:
        if remaining == 0:
            break
        symbol = index.symbols[neighbor_id]
        source = source_lines(symbol.file)
        end = min(symbol.end_line, len(source))
        start = symbol.start_line
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
        end = min(getattr(node, "end_lineno", line), len(source)) if node is not None else line
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
        {
            "caller": edge.caller,
            "callee": edge.callee,
            "file": index.symbols[edge.caller].file,
            "line": edge.line,
            "via_reexports": [asdict(hop) for hop in edge.via_reexports],
        }
        for edge in index.call_edges
        if edge.caller == symbol_id or edge.callee == symbol_id
    ]
    semantic_evidence = [
        _semantic_edge_data(edge, symbol_id)
        for edge in index.semantic_edges
        if edge.source_symbol == symbol_id or edge.target_symbol == symbol_id
    ]
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
    }


def build_impact(index: RepoIndex, symbol_id: str, depth: int = 2) -> dict:
    """Follow reverse static call edges; this is not runtime coverage."""
    target = _require_symbol(index, symbol_id)
    if depth < 1:
        raise ValueError("depth must be at least 1")
    incoming: dict[str, set[str]] = defaultdict(set)
    for edge in index.call_edges:
        incoming[edge.callee].add(edge.caller)
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
            affected.append({"symbol": caller, "distance": distance + 1, "path": caller_path})
            queue.append((caller, distance + 1, caller_path))
    affected.sort(key=lambda item: (item["distance"], item["symbol"]))
    imports = [
        {"source": edge.source, "target": edge.target, "line": edge.line}
        for edge in index.import_edges
        if edge.target == target.file and edge.source != target.file
    ]
    semantic_relations = [
        _semantic_edge_data(edge, symbol_id)
        for edge in index.semantic_edges
        if edge.source_symbol == symbol_id or edge.target_symbol == symbol_id
    ]
    return {
        "schema_version": 2,
        "symbol": symbol_id,
        "depth": depth,
        "affected_symbols": affected,
        "module_importers": sorted({item["source"] for item in imports}),
        "import_evidence": imports,
        "semantic_relations": semantic_relations,
    }
