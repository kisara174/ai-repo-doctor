"""Resolve local imports and calls conservatively, then find import cycles."""

from collections import defaultdict
from pathlib import PurePosixPath

from .model import CallEdge, CallSite, ImportEdge, ImportRef, RepoIndex, Symbol


def _module_names(path: str) -> set[str]:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    names = {".".join(parts)} if parts else set()
    if parts and parts[0] == "src" and len(parts) > 1:
        names.add(".".join(parts[1:]))
    return names


def _base_module(ref: ImportRef) -> str | None:
    if ref.level == 0:
        return ref.module
    package = list(PurePosixPath(ref.file).parts[:-1])
    if package and package[0] == "src":
        package.pop(0)
    climb = ref.level - 1
    if not package or climb >= len(package):
        return None
    prefix = package[: len(package) - climb]
    if ref.module:
        prefix.extend(ref.module.split("."))
    return ".".join(prefix)


def _module_lookup(index: RepoIndex) -> dict[str, str]:
    candidates: dict[str, set[str]] = defaultdict(set)
    for file in index.files:
        for name in _module_names(file.path):
            candidates[name].add(file.path)
    return {name: next(iter(paths)) for name, paths in candidates.items() if len(paths) == 1}


def _alias_targets(ref: ImportRef, modules: dict[str, str], symbols: dict[str, Symbol]) -> set[tuple[str, str]]:
    base = _base_module(ref)
    if base is None:
        return set()
    if ref.name is None:
        # `import pkg.mod` binds `pkg`; `import pkg.mod as pkg` binds the submodule.
        bound_module = base if ref.explicit_alias else base.split(".", 1)[0]
        target = modules.get(bound_module)
        return {("module", target)} if target else set()
    targets: set[tuple[str, str]] = set()
    if ref.name == "*":
        return targets
    child = f"{base}.{ref.name}" if base else ref.name
    if child in modules:
        targets.add(("module", modules[child]))
    base_file = modules.get(base)
    if base_file:
        symbol_id = f"{base_file}::{ref.name}"
        if symbol_id in symbols:
            targets.add(("symbol", symbol_id))
    return targets


def _import_targets(ref: ImportRef, modules: dict[str, str]) -> set[str]:
    base = _base_module(ref)
    if base is None:
        return set()
    targets = {modules[base]} if base in modules else set()
    if ref.name and ref.name != "*":
        child = f"{base}.{ref.name}" if base else ref.name
        if child in modules:
            targets.add(modules[child])
    return targets


def _unique_alias(
    aliases: dict[tuple[str, str | None, str], set[tuple[str, str]]],
    file: str,
    scope: str | None,
    name: str,
) -> tuple[str, str] | None:
    targets = aliases.get((file, scope, name), set())
    return next(iter(targets)) if len(targets) == 1 else None


def _resolve_call(
    call: CallSite,
    index: RepoIndex,
    aliases: dict[tuple[str, str | None, str], set[tuple[str, str]]],
) -> str | None:
    caller = index.symbols.get(call.caller)
    if caller is None or not call.name:
        return None

    if call.receiver is None and call.expression == call.name:
        nested = f"{caller.file}::{caller.qualname}.{call.name}"
        if nested in index.symbols:
            return nested
        if call.name in caller.local_bindings:
            return None
        if call.name in index.module_bindings.get(caller.file, set()):
            return None
        same_file = f"{caller.file}::{call.name}"
        module_alias = _unique_alias(aliases, caller.file, None, call.name)
        if (caller.file, None, call.name) in aliases and (module_alias is None or module_alias[0] != "symbol"):
            return None
        candidates = {same_file} if same_file in index.symbols else set()
        if module_alias and module_alias[0] == "symbol":
            candidates.add(module_alias[1])
        return next(iter(candidates)) if len(candidates) == 1 else None

    receiver = call.receiver
    if receiver is None or call.expression != f"{receiver}.{call.name}":
        return None
    if receiver == "self" and caller.kind == "method" and caller.parent:
        target = f"{caller.parent}.{call.name}"
        return target if target in index.symbols else None
    if receiver in index.module_bindings.get(caller.file, set()):
        return None
    if receiver in caller.local_bindings:
        return None
    alias = _unique_alias(aliases, caller.file, None, receiver)
    if (caller.file, None, receiver) in aliases and alias is None:
        return None
    if alias and f"{caller.file}::{receiver}" in index.symbols:
        return None
    if alias:
        target = f"{alias[1]}::{call.name}" if alias[0] == "module" else f"{alias[1]}.{call.name}"
        return target if target in index.symbols else None
    target = f"{caller.file}::{receiver}.{call.name}"
    return target if target in index.symbols else None


def _import_cycles(index: RepoIndex) -> list[list[str]]:
    neighbors: dict[str, set[str]] = {item.path: set() for item in index.files}
    reverse: dict[str, set[str]] = {item.path: set() for item in index.files}
    for edge in index.import_edges:
        neighbors[edge.source].add(edge.target)
        reverse[edge.target].add(edge.source)
    visited: set[str] = set()
    finished: list[str] = []
    for start in sorted(neighbors):
        if start in visited:
            continue
        visited.add(start)
        pending = [(start, iter(sorted(neighbors[start])))]
        while pending:
            node, children = pending[-1]
            target = next(children, None)
            if target is None:
                finished.append(node)
                pending.pop()
            elif target not in visited:
                visited.add(target)
                pending.append((target, iter(sorted(neighbors[target]))))

    visited.clear()
    cycles: list[list[str]] = []
    for start in reversed(finished):
        if start in visited:
            continue
        component: list[str] = []
        pending = [start]
        visited.add(start)
        while pending:
            node = pending.pop()
            component.append(node)
            for source in sorted(reverse[node]):
                if source not in visited:
                    visited.add(source)
                    pending.append(source)
        if len(component) > 1 or start in neighbors[start]:
            cycles.append(sorted(component))
    return sorted(cycles)


def resolve_graph(index: RepoIndex) -> None:
    """Populate edges that refer to a unique source-defined local target."""
    modules = _module_lookup(index)
    aliases: dict[tuple[str, str | None, str], set[tuple[str, str]]] = defaultdict(set)
    for ref in index.imports:
        for target in _import_targets(ref, modules):
            if target != ref.file or ref.level == 0 or ref.name is None:
                index.import_edges.append(ImportEdge(ref.file, target, ref.line))
        if ref.owner is None:
            targets = _alias_targets(ref, modules, index.symbols)
            aliases[(ref.file, None, ref.alias)].update(targets or {("unknown", "")})
    index.import_edges = sorted(set(index.import_edges), key=lambda edge: (edge.source, edge.line, edge.target))
    for call in index.calls:
        target = _resolve_call(call, index, aliases)
        if target:
            index.call_edges.append(CallEdge(call.caller, target, call.line))
    index.call_edges.sort(key=lambda edge: (edge.caller, edge.line, edge.callee))
    index.import_cycles = _import_cycles(index)
