"""Build an in-memory snapshot of the current Python working tree."""

from dataclasses import replace
from pathlib import Path

from .graph import resolve_graph
from .model import RepoIndex
from .parser import parse_python_file
from .scanner import discover_python_files


def build_index(root: Path) -> RepoIndex:
    root = Path(root).resolve()
    root_stat = root.stat()
    root_identity = (root_stat.st_dev, root_stat.st_ino)
    paths, scan_mode = discover_python_files(root)
    index = RepoIndex(root=root, scan_mode=scan_mode, root_identity=root_identity)
    candidates_by_id = {}
    for path in paths:
        parsed = parse_python_file(root, path, root_identity=root_identity)
        index.files.append(parsed.file)
        for symbol in parsed.symbols:
            candidates_by_id.setdefault(symbol.id, []).append(symbol)
        index.imports.extend(parsed.imports)
        index.calls.extend(parsed.calls)
        index.module_bindings[path] = parsed.module_bindings
        if parsed.error:
            index.parse_errors.append(parsed.error)
    for symbol_id, candidates in candidates_by_id.items():
        if len(candidates) == 1:
            index.symbols[symbol_id] = candidates[0]
            continue
        overload_candidates = [symbol for symbol in candidates if symbol.is_overload]
        concrete_candidates = [symbol for symbol in candidates if not symbol.is_overload]
        if (
            len(concrete_candidates) == 1
            and len(overload_candidates) == len(candidates) - 1
            and all(symbol.overload_signature is not None for symbol in overload_candidates)
        ):
            overload_signatures = tuple(
                symbol.overload_signature
                for symbol in sorted(overload_candidates, key=lambda candidate: candidate.start_line)
                if symbol.overload_signature is not None
            )
            index.symbols[symbol_id] = replace(concrete_candidates[0], overloads=overload_signatures)
        else:
            index.ambiguous_symbols.add(symbol_id)
    for symbol_id, symbol in list(index.symbols.items()):
        if any(f"{symbol.file}::{'.'.join(symbol.qualname.split('.')[:part])}" in index.ambiguous_symbols for part in range(1, len(symbol.qualname.split('.')))):
            del index.symbols[symbol_id]
            index.ambiguous_symbols.add(symbol_id)
    resolve_graph(index)
    return index
