"""Resolve narrowly supported decorator-based relationships without execution."""

import ast
from dataclasses import replace

from .graph import _module_candidates, _resolve_export
from .model import DecoratorRef, ImportRef, RepoIndex, SemanticEdge, Symbol


_CLICK_API_NAMES = {"group", "command"}


def _has_module_binding_conflict(
    index: RepoIndex,
    file: str,
    name: str,
    *,
    allow_symbol_id: str | None = None,
    allow_import_ref: ImportRef | None = None,
) -> bool:
    symbol_id = f"{file}::{name}"
    return (
        name in index.module_bindings.get(file, set())
        or (symbol_id in index.symbols and symbol_id != allow_symbol_id)
        or symbol_id in index.ambiguous_symbols
        or any(
            ref is not allow_import_ref
            and ref.file == file
            and ref.owner is None
            and ref.alias == name
            for ref in index.imports
        )
        or any(ref.file == file and ref.owner is None and ref.name == "*" for ref in index.imports)
    )


def _local_click_candidates(index: RepoIndex) -> set[str]:
    return _module_candidates(index).get("click", set())


def _click_api_is_available(index: RepoIndex, name: str) -> bool:
    candidates = _local_click_candidates(index)
    if not candidates:
        # An explicit `click` import with no local module refers to the named
        # external package; it is safe to recognize its documented API names.
        return True
    if len(candidates) != 1:
        return False
    resolved = _resolve_export(index, next(iter(candidates)), name, set())
    if resolved is None:
        return False
    symbol = index.symbols.get(resolved[0])
    return symbol is not None and symbol.kind == "function"


def _click_group_class_is_available(index: RepoIndex) -> bool:
    candidates = _local_click_candidates(index)
    if not candidates:
        return True
    if len(candidates) != 1:
        return False
    resolved = _resolve_export(index, next(iter(candidates)), "Group", set())
    if resolved is None:
        return False
    symbol = index.symbols.get(resolved[0])
    return symbol is not None and symbol.kind == "class"


def _module_import_is_unshadowed(
    index: RepoIndex,
    file: str,
    alias: str,
    selected_ref: ImportRef,
) -> bool:
    refs = [
        ref
        for ref in index.imports
        if ref.file == file and ref.owner is None and ref.alias == alias
    ]
    return (
        len(refs) == 1
        and refs[0] == selected_ref
        and selected_ref.is_unconditional_module_level
        and not _has_module_binding_conflict(
            index,
            file,
            alias,
            allow_import_ref=selected_ref,
        )
    )


def _click_api_aliases(index: RepoIndex) -> dict[tuple[str, str], str]:
    aliases: dict[tuple[str, str], str] = {}
    for ref in index.imports:
        if ref.owner is not None or ref.level != 0 or ref.module != "click":
            continue
        if not _module_import_is_unshadowed(index, ref.file, ref.alias, ref):
            continue
        if ref.name is None:
            if any(_click_api_is_available(index, name) for name in _CLICK_API_NAMES):
                aliases[(ref.file, ref.alias)] = "click"
        elif ref.name in _CLICK_API_NAMES and _click_api_is_available(index, ref.name):
            aliases[(ref.file, ref.alias)] = f"click.{ref.name}"
    return aliases


def _click_group_import_aliases(index: RepoIndex) -> set[tuple[str, str]]:
    if not _click_group_class_is_available(index):
        return set()
    aliases = set()
    for ref in index.imports:
        if ref.owner is not None or ref.level != 0 or ref.module != "click" or ref.name != "Group":
            continue
        if _module_import_is_unshadowed(index, ref.file, ref.alias, ref):
            aliases.add((ref.file, ref.alias))
    return aliases


def _class_inherits_click_group(
    index: RepoIndex,
    symbol_id: str,
    module_aliases: dict[tuple[str, str], str],
    group_aliases: set[tuple[str, str]],
    visiting: set[str] | None = None,
) -> bool:
    """Prove a same-module class chain reaches Click's Group base class."""
    symbol = index.symbols.get(symbol_id)
    if (
        symbol is None
        or symbol.kind != "class"
        or symbol.parent is not None
        or symbol_id in index.ambiguous_symbols
        or _has_module_binding_conflict(
            index, symbol.file, symbol.name, allow_symbol_id=symbol_id
        )
    ):
        return False

    seen = set() if visiting is None else visiting
    if symbol_id in seen:
        return False
    seen.add(symbol_id)

    for expression in symbol.base_expressions:
        try:
            base = ast.parse(expression, mode="eval").body
        except SyntaxError:
            continue

        if isinstance(base, ast.Name):
            if (symbol.file, base.id) in group_aliases:
                return True
            local_base_id = f"{symbol.file}::{base.id}"
            local_base = index.symbols.get(local_base_id)
            if local_base is not None and _class_inherits_click_group(
                index, local_base_id, module_aliases, group_aliases, seen
            ):
                return True
        elif (
            isinstance(base, ast.Attribute)
            and isinstance(base.value, ast.Name)
            and base.attr == "Group"
            and module_aliases.get((symbol.file, base.value.id)) == "click"
            and _click_group_class_is_available(index)
        ):
            return True

    return False


def _parent_scope_shadows(index: RepoIndex, symbol: Symbol, name: str) -> bool:
    parent_id = symbol.parent
    while parent_id is not None:
        parent = index.symbols.get(parent_id)
        if parent is None:
            return True
        if parent.kind == "class":
            # Class bodies have their own decorator evaluation scope, but the
            # parser does not record class-body bindings yet.
            return True
        if name in parent.local_bindings:
            return True
        parent_id = parent.parent
    return False


def _decorator_target(expression: str) -> ast.expr | None:
    try:
        node = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return None
    return node.func if isinstance(node, ast.Call) else None


def _click_decorator_identity(
    index: RepoIndex,
    symbol: Symbol,
    decorator: DecoratorRef,
    aliases: dict[tuple[str, str], str],
) -> str | None:
    if decorator.recognized in {"click.group", "click.command"}:
        return decorator.recognized
    target = _decorator_target(decorator.expression)
    if isinstance(target, ast.Name):
        if _parent_scope_shadows(index, symbol, target.id):
            return None
        identity = aliases.get((symbol.file, target.id))
        return identity if identity in {"click.group", "click.command"} else None
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.attr in _CLICK_API_NAMES
    ):
        module_alias = target.value.id
        if _parent_scope_shadows(index, symbol, module_alias):
            return None
        if aliases.get((symbol.file, module_alias)) != "click":
            return None
        if not _click_api_is_available(index, target.attr):
            return None
        return f"click.{target.attr}"
    return None


def _mark_click_decorators(
    index: RepoIndex,
    aliases: dict[tuple[str, str], str],
) -> None:
    for symbol_id, symbol in list(index.symbols.items()):
        decorators = []
        changed = False
        for decorator in symbol.decorators:
            identity = _click_decorator_identity(index, symbol, decorator, aliases)
            if identity is not None and decorator.recognized != identity:
                decorators.append(replace(decorator, recognized=identity))
                changed = True
            else:
                decorators.append(decorator)
        if changed:
            index.symbols[symbol_id] = replace(symbol, decorators=tuple(decorators))


def _group_callbacks(
    index: RepoIndex,
    aliases: dict[tuple[str, str], str],
) -> set[str]:
    groups = set()
    for symbol in index.symbols.values():
        if symbol.kind != "function" or symbol.parent is not None:
            continue
        if any(
            _click_decorator_identity(index, symbol, decorator, aliases) == "click.group"
            for decorator in symbol.decorators
        ):
            groups.add(symbol.id)
    return groups


def _command_callbacks(
    index: RepoIndex,
    aliases: dict[tuple[str, str], str],
) -> set[str]:
    callbacks = set()
    for symbol in index.symbols.values():
        if symbol.kind != "function" or symbol.parent is not None:
            continue
        if _has_module_binding_conflict(
            index,
            symbol.file,
            symbol.name,
            allow_symbol_id=symbol.id,
        ):
            continue
        if any(
            _click_decorator_identity(index, symbol, decorator, aliases)
            in {"click.command", "click.group"}
            for decorator in symbol.decorators
        ):
            callbacks.add(symbol.id)
    return callbacks


def _registration_decorator(decorator: DecoratorRef) -> tuple[str, str] | None:
    try:
        expression = ast.parse(decorator.expression, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(expression, ast.Call):
        return None
    function = expression.func
    if (
        isinstance(function, ast.Attribute)
        and function.attr in {"command", "group"}
        and isinstance(function.value, ast.Name)
    ):
        return function.value.id, function.attr
    return None


def _registration_edges(
    index: RepoIndex,
    groups: set[str],
) -> list[SemanticEdge]:
    candidates = []
    for callback in index.symbols.values():
        if callback.kind != "function" or callback.parent is not None:
            continue
        if _has_module_binding_conflict(
            index,
            callback.file,
            callback.name,
            allow_symbol_id=callback.id,
        ):
            continue
        for decorator in callback.decorators:
            registration = _registration_decorator(decorator)
            if registration is not None:
                candidates.append((callback, decorator, registration))

    edges: set[SemanticEdge] = set()
    while True:
        new_groups = set()
        for callback, decorator, (receiver, registration_kind) in candidates:
            if _parent_scope_shadows(index, callback, receiver):
                continue
            source_symbol = f"{callback.file}::{receiver}"
            group = index.symbols.get(source_symbol)
            if (
                source_symbol not in groups
                or group is None
                or group.file != callback.file
                or group.kind != "function"
                or group.parent is not None
                or _has_module_binding_conflict(
                    index,
                    callback.file,
                    receiver,
                    allow_symbol_id=source_symbol,
                )
            ):
                continue
            edges.add(
                SemanticEdge(
                    kind="command_registration",
                    source_symbol=source_symbol,
                    target_symbol=callback.id,
                    evidence_file=callback.file,
                    line=decorator.line,
                )
            )
            if registration_kind == "group":
                new_groups.add(callback.id)
        new_groups.difference_update(groups)
        if not new_groups:
            return list(edges)
        groups.update(new_groups)


def _explicit_registration_edges(
    index: RepoIndex,
    groups: set[str],
    callbacks: set[str],
    module_aliases: dict[tuple[str, str], str],
    group_aliases: set[tuple[str, str]],
) -> list[SemanticEdge]:
    edges = set()
    for registration in index.registration_calls:
        caller = index.symbols.get(registration.caller) if registration.caller else None
        if caller is not None:
            if registration.callback in caller.local_bindings:
                continue
            if (
                registration.receiver != "self"
                and registration.receiver in caller.local_bindings
            ):
                continue

        source_symbol: str | None = None
        if registration.receiver == "self":
            class_owner = registration.class_owner
            if (
                class_owner is None
                or caller is None
                or caller.kind != "method"
                or caller.parent != class_owner
            ):
                continue
            class_symbol = index.symbols.get(class_owner)
            if (
                class_symbol is None
                or not _class_inherits_click_group(
                    index,
                    class_owner,
                    module_aliases,
                    group_aliases,
                )
            ):
                continue
            source_symbol = class_owner
        else:
            source_symbol = f"{registration.file}::{registration.receiver}"
            group = index.symbols.get(source_symbol)
            if (
                source_symbol not in groups
                or group is None
                or group.kind != "function"
                or group.parent is not None
                or group.file != registration.file
                or _has_module_binding_conflict(
                    index,
                    registration.file,
                    registration.receiver,
                    allow_symbol_id=source_symbol,
                )
            ):
                continue

        target_symbol = f"{registration.file}::{registration.callback}"
        callback = index.symbols.get(target_symbol)
        if (
            target_symbol not in callbacks
            or callback is None
            or callback.file != registration.file
            or _has_module_binding_conflict(
                index,
                registration.file,
                registration.callback,
                allow_symbol_id=target_symbol,
            )
        ):
            continue

        edges.add(
            SemanticEdge(
                kind="command_registration",
                source_symbol=source_symbol,
                target_symbol=target_symbol,
                evidence_file=registration.file,
                line=registration.line,
            )
        )
    return list(edges)


def resolve_semantic_edges(index: RepoIndex) -> None:
    """Add supported Click relationships after ordinary graph resolution."""
    aliases = _click_api_aliases(index)
    group_aliases = _click_group_import_aliases(index)
    _mark_click_decorators(index, aliases)
    groups = _group_callbacks(index, aliases)
    decorator_registration_edges = _registration_edges(index, groups)
    index.semantic_edges.extend(decorator_registration_edges)
    callbacks = _command_callbacks(index, aliases)
    callbacks.update(edge.target_symbol for edge in decorator_registration_edges)
    index.semantic_edges.extend(
        _explicit_registration_edges(index, groups, callbacks, aliases, group_aliases)
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
