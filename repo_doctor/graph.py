"""Resolve local imports and calls conservatively, then find import cycles."""

from collections import defaultdict
from pathlib import PurePosixPath

from .model import (
    CallEdge,
    CallSite,
    ExportHop,
    ImportEdge,
    ImportRef,
    LocalConstructor,
    RepoIndex,
    SemanticEdge,
    Symbol,
)


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


def _module_candidates(index: RepoIndex) -> dict[str, set[str]]:
    candidates: dict[str, set[str]] = defaultdict(set)
    for file in index.files:
        for name in _module_names(file.path):
            candidates[name].add(file.path)
    return candidates


def _module_lookup(index: RepoIndex) -> dict[str, str]:
    candidates = _module_candidates(index)
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


def _resolve_class_expression(
    constructor: LocalConstructor,
    file: str,
    caller: Symbol,
    index: RepoIndex,
    aliases: dict[tuple[str, str | None, str], set[tuple[str, str]]],
) -> str | None:
    parts = constructor.expression.split(".")
    if parts[0] in caller.local_bindings or parts[0] in index.module_bindings.get(file, set()):
        return None
    if len(parts) == 1:
        alias_key = (file, None, parts[0])
        alias = _unique_alias(aliases, file, None, parts[0])
        if alias_key in aliases:
            local_symbol = index.symbols.get(f"{file}::{parts[0]}")
            if local_symbol is not None:
                return None
            if alias is None or alias[0] != "symbol":
                return None
            symbol_id = alias[1]
        else:
            symbol_id = f"{file}::{parts[0]}"
    elif len(parts) == 2:
        alias_key = (file, None, parts[0])
        alias = _unique_alias(aliases, file, None, parts[0])
        if alias_key not in aliases or alias is None or alias[0] != "module":
            return None
        if f"{file}::{parts[0]}" in index.symbols:
            return None
        if parts[1] in index.module_bindings.get(alias[1], set()):
            return None
        symbol_id = f"{alias[1]}::{parts[1]}"
    else:
        return None
    symbol = index.symbols.get(symbol_id)
    if symbol is None or symbol.kind != "class":
        return None
    if constructor.context_method:
        enter = index.symbols.get(f"{symbol_id}.{constructor.context_method}")
        is_async_context = constructor.context_method == "__aenter__"
        exit_method = "__aexit__" if is_async_context else "__exit__"
        exit_symbol = index.symbols.get(f"{symbol_id}.{exit_method}")
        if (
            enter is None
            or not enter.returns_self
            or enter.is_async != is_async_context
            or exit_symbol is None
        ):
            return None
    return symbol_id


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
    if receiver in caller.local_bindings:
        constructor = dict(caller.local_constructors).get(receiver)
        if constructor is not None and (constructor.line, constructor.column) >= (call.line, call.column):
            return None
        class_id = (
            _resolve_class_expression(constructor, caller.file, caller, index, aliases)
            if constructor is not None
            else None
        )
        target = f"{class_id}.{call.name}" if class_id else None
        symbol = index.symbols.get(target) if target else None
        return target if symbol is not None and symbol.kind == "method" else None
    if receiver in index.module_bindings.get(caller.file, set()):
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


def _module_level_imports(index: RepoIndex, file: str, name: str) -> list[ImportRef]:
    return sorted(
        (
            ref
            for ref in index.imports
            if ref.file == file
            and ref.owner is None
            and ref.name is not None
            and ref.name != "*"
            and ref.alias == name
        ),
        key=lambda ref: (ref.line, ref.module, ref.name or "", ref.alias),
    )


def _submodule_candidates(index: RepoIndex, file: str, name: str) -> set[str]:
    candidates = _module_candidates(index)
    paths: set[str] = set()
    for module_name in _module_names(file):
        paths.update(candidates.get(f"{module_name}.{name}", set()))
    return paths


def _resolve_export(
    index: RepoIndex,
    file: str,
    name: str,
    active: set[tuple[str, str]],
) -> tuple[str, tuple[ExportHop, ...]] | None:
    """Resolve one explicit module binding to a local symbol with its re-export path."""
    key = (file, name)
    if key in active:
        return None
    active.add(key)
    try:
        return _resolve_direct_symbol_or_explicit_import(index, file, name, active)
    finally:
        active.remove(key)


def _resolve_direct_symbol_or_explicit_import(
    index: RepoIndex,
    file: str,
    name: str,
    active: set[tuple[str, str]],
) -> tuple[str, tuple[ExportHop, ...]] | None:
    symbol_id = f"{file}::{name}"
    if symbol_id in index.ambiguous_symbols:
        return None
    direct_symbol = symbol_id in index.symbols
    imports = _module_level_imports(index, file, name)
    submodules = _submodule_candidates(index, file, name)
    has_wildcard_import = any(
        ref.file == file and ref.owner is None and ref.name == "*"
        for ref in index.imports
    )

    # A conditional binding, explicit import collision, or local submodule
    # collision means the module attribute cannot be tied to one symbol.
    if has_wildcard_import:
        return None
    if name in index.module_bindings.get(file, set()):
        return None
    if submodules and (direct_symbol or imports):
        return None
    if direct_symbol:
        return (symbol_id, ()) if not imports else None
    if len(imports) != 1:
        return None

    ref = imports[0]
    if not ref.is_unconditional_module_level:
        return None
    base = _base_module(ref)
    if base is None:
        return None
    modules = _module_lookup(index)
    base_file = modules.get(base)
    if base_file is None:
        return None

    child_module_exists = f"{base}.{ref.name}" in _module_candidates(index)
    resolved = _resolve_export(index, base_file, ref.name, active)
    if child_module_exists or resolved is None:
        return None
    target_symbol, inner_hops = resolved
    hop = ExportHop(file, name, ref.line)
    return target_symbol, (hop, *inner_hops)


def _reexport_binding_for_call(
    call: CallSite,
    index: RepoIndex,
    aliases: dict[tuple[str, str | None, str], set[tuple[str, str]]],
) -> tuple[str, str] | None:
    caller = index.symbols.get(call.caller)
    if caller is None:
        return None

    if call.receiver is None and call.expression == call.name:
        if (
            call.name in caller.local_bindings
            or call.name in index.module_bindings.get(call.file, set())
            or f"{call.file}::{call.name}" in index.symbols
        ):
            return None
        imports = _module_level_imports(index, call.file, call.name)
        if len(imports) != 1 or not imports[0].is_unconditional_module_level:
            return None
        ref = imports[0]
        base = _base_module(ref)
        module_file = _module_lookup(index).get(base) if base is not None else None
        if module_file is None:
            return None
        return module_file, ref.name

    receiver = call.receiver
    if receiver is None or call.expression != f"{receiver}.{call.name}":
        return None
    if (
        receiver in caller.local_bindings
        or receiver in index.module_bindings.get(call.file, set())
        or f"{call.file}::{receiver}" in index.symbols
    ):
        return None
    imports = [
        ref
        for ref in index.imports
        if ref.file == call.file and ref.owner is None and ref.alias == receiver
    ]
    if len(imports) != 1 or not imports[0].is_unconditional_module_level:
        return None
    alias = _unique_alias(aliases, call.file, None, receiver)
    if alias is None or alias[0] != "module":
        return None
    return alias[1], call.name


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

    for ref in index.imports:
        if (
            ref.owner is not None
            or not ref.is_unconditional_module_level
            or ref.name is None
            or ref.name == "*"
        ):
            continue
        resolved = _resolve_export(index, ref.file, ref.alias, set())
        if resolved is None:
            continue
        target_symbol, _hops = resolved
        index.semantic_edges.append(
            SemanticEdge(
                kind="reexport",
                target_symbol=target_symbol,
                evidence_file=ref.file,
                line=ref.line,
                source_file=ref.file,
                exported_name=ref.alias,
            )
        )
    index.semantic_edges = sorted(
        set(index.semantic_edges),
        key=lambda edge: (
            edge.evidence_file,
            edge.line,
            edge.kind,
            edge.source_symbol or "",
            edge.exported_name or "",
            edge.target_symbol,
        ),
    )

    for call in index.calls:
        target = _resolve_call(call, index, aliases)
        via_reexports: tuple[ExportHop, ...] = ()
        binding = _reexport_binding_for_call(call, index, aliases)
        if binding is not None:
            reexport = _resolve_export(index, binding[0], binding[1], set())
            if reexport is None:
                target = None
            else:
                target, via_reexports = reexport
        if target:
            index.call_edges.append(CallEdge(call.caller, target, call.line, via_reexports))
    index.call_edges.sort(key=lambda edge: (edge.caller, edge.line, edge.callee))
    index.import_cycles = _import_cycles(index)
