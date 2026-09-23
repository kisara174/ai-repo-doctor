"""Retrieve bounded source context and reverse dependency impact."""

from collections import defaultdict, deque

from .model import RepoIndex, Symbol
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


def build_context(index: RepoIndex, symbol_id: str, max_lines: int = 120) -> dict:
    """Return target-first one-hop context with a physical source-line budget."""
    target = _require_symbol(index, symbol_id)
    if max_lines < 1:
        raise ValueError("max_lines must be at least 1")

    candidates: list[tuple[str, str]] = [(target.id, "target")]
    seen = {target.id}

    def add(symbols: set[str], relation: str) -> None:
        for neighbor_id in sorted(symbols, key=lambda item: (index.symbols[item].file, index.symbols[item].start_line, item)):
            if neighbor_id not in seen:
                seen.add(neighbor_id)
                candidates.append((neighbor_id, relation))

    add({edge.callee for edge in index.call_edges if edge.caller == symbol_id}, "callee")
    callers = {edge.caller for edge in index.call_edges if edge.callee == symbol_id}
    test_files = {file.path for file in index.files if file.is_test}
    tests = {item for item in callers if index.symbols[item].file in test_files}
    add(callers - tests, "caller")
    add(tests, "related_test")

    remaining = max_lines
    blocks: list[dict] = []
    for neighbor_id, relation in candidates:
        if remaining == 0:
            break
        symbol = index.symbols[neighbor_id]
        source = _read_lines(index, symbol.file)
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

    direct_edges = [
        {"caller": edge.caller, "callee": edge.callee, "file": index.symbols[edge.caller].file, "line": edge.line}
        for edge in index.call_edges
        if edge.caller == symbol_id or edge.callee == symbol_id
    ]
    return {
        "schema_version": 1,
        "symbol": symbol_id,
        "max_lines": max_lines,
        "blocks": blocks,
        "call_evidence": direct_edges,
        "budget_exhausted": any(block["truncated"] for block in blocks) or len(blocks) < len(candidates),
        "omitted_symbols": len(candidates) - len(blocks),
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
    return {
        "schema_version": 1,
        "symbol": symbol_id,
        "depth": depth,
        "affected_symbols": affected,
        "module_importers": sorted({item["source"] for item in imports}),
        "import_evidence": imports,
    }
