"""Build an in-memory snapshot of the current Python working tree."""

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
    for path in paths:
        parsed = parse_python_file(root, path, root_identity=root_identity)
        index.files.append(parsed.file)
        for symbol in parsed.symbols:
            if symbol.id in index.ambiguous_symbols:
                continue
            if symbol.id in index.symbols:
                del index.symbols[symbol.id]
                index.ambiguous_symbols.add(symbol.id)
            else:
                index.symbols[symbol.id] = symbol
        index.imports.extend(parsed.imports)
        index.calls.extend(parsed.calls)
        index.module_bindings[path] = parsed.module_bindings
        if parsed.error:
            index.parse_errors.append(parsed.error)
    for symbol_id, symbol in list(index.symbols.items()):
        if any(f"{symbol.file}::{'.'.join(symbol.qualname.split('.')[:part])}" in index.ambiguous_symbols for part in range(1, len(symbol.qualname.split('.')))):
            del index.symbols[symbol_id]
            index.ambiguous_symbols.add(symbol_id)
    resolve_graph(index)
    return index
