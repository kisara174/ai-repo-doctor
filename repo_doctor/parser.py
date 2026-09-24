"""Extract Python structure without importing or executing scanned code."""

import ast
from collections import defaultdict
from pathlib import Path

from .model import (
    CallSite,
    DecoratorRef,
    FileRecord,
    ImportRef,
    LocalConstructor,
    OverloadSignature,
    ParsedFile,
    ParseError,
    Symbol,
)
from .source import read_source


def _bindings(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    args = node.args
    names = {arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            names.add(child.id)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child is not node:
            names.add(child.name)
        elif isinstance(child, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in child.names)
        elif isinstance(child, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in child.names)
        elif isinstance(child, ast.MatchAs) and child.name:
            names.add(child.name)
        elif isinstance(child, ast.MatchStar) and child.name:
            names.add(child.name)
        elif isinstance(child, ast.MatchMapping) and child.rest:
            names.add(child.rest)
    return frozenset(names)


def _constructor_expression(value: ast.expr) -> str | None:
    if not isinstance(value, ast.Call):
        return None
    func = value.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return None


def _end_position(node: ast.AST) -> tuple[int, int]:
    line = getattr(node, "end_lineno", None) or getattr(node, "lineno", 1)
    column = getattr(node, "end_col_offset", None)
    if column is None:
        column = getattr(node, "col_offset", 0)
    return line, column


def _local_constructors(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[tuple[str, LocalConstructor], ...]:
    """Find uniquely assigned constructors in straight-line local scope."""
    scope_nodes: list[tuple[ast.AST, bool]] = []
    pending = [(child, False) for child in reversed(node.body)]
    conditional = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.TryStar, ast.Match)
    while pending:
        current, guarded = pending.pop()
        scope_nodes.append((current, guarded))
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        child_guarded = guarded or isinstance(current, conditional) or isinstance(current, (ast.With, ast.AsyncWith))
        pending.extend((child, child_guarded) for child in reversed(list(ast.iter_child_nodes(current))))

    writes: dict[str, list[LocalConstructor | None]] = defaultdict(list)
    recognized_stores: set[int] = set()

    def bind_target(target: ast.expr, constructor: LocalConstructor | None) -> None:
        if isinstance(target, ast.Name):
            writes[target.id].append(constructor)
            recognized_stores.add(id(target))
            return
        for child in ast.walk(target):
            if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                writes[child.id].append(None)
                recognized_stores.add(id(child))

    def add_nested_nonlocal_writes(scope: ast.AST) -> None:
        for descendant in ast.walk(scope):
            if isinstance(descendant, ast.Nonlocal):
                for name in descendant.names:
                    writes[name].append(None)

    arguments = node.args
    for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
        writes[argument.arg].append(None)
    if arguments.vararg:
        writes[arguments.vararg.arg].append(None)
    if arguments.kwarg:
        writes[arguments.kwarg.arg].append(None)

    for current, guarded in scope_nodes:
        if isinstance(current, ast.Assign):
            expression = _constructor_expression(current.value)
            line, column = _end_position(current)
            constructor = (
                LocalConstructor(expression, line, column)
                if expression is not None and not guarded
                else None
            )
            for target in current.targets:
                bind_target(target, constructor)
        elif isinstance(current, ast.AnnAssign):
            expression = _constructor_expression(current.value) if current.value else None
            line, column = _end_position(current)
            constructor = (
                LocalConstructor(expression, line, column)
                if expression is not None and not guarded
                else None
            )
            bind_target(current.target, constructor)
        elif isinstance(current, (ast.With, ast.AsyncWith)):
            for item in current.items:
                if item.optional_vars is not None:
                    expression = _constructor_expression(item.context_expr)
                    line, column = _end_position(item.context_expr)
                    context_method = "__aenter__" if isinstance(current, ast.AsyncWith) else "__enter__"
                    constructor = (
                        LocalConstructor(expression, line, column, context_method=context_method)
                        if expression is not None and not guarded
                        else None
                    )
                    bind_target(item.optional_vars, constructor)
        elif isinstance(current, (ast.Import, ast.ImportFrom)):
            for alias in current.names:
                if alias.name != "*":
                    bound = alias.asname or (alias.name.split(".", 1)[0] if isinstance(current, ast.Import) else alias.name)
                    writes[bound].append(None)
        elif isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            writes[current.name].append(None)
            add_nested_nonlocal_writes(current)
        elif isinstance(current, ast.ExceptHandler) and current.name:
            writes[current.name].append(None)
        elif isinstance(current, (ast.Global, ast.Nonlocal)):
            for name in current.names:
                writes[name].append(None)

    for current, _guarded in scope_nodes:
        if isinstance(current, ast.Name) and isinstance(current.ctx, (ast.Store, ast.Del)) and id(current) not in recognized_stores:
            writes[current.id].append(None)
        elif isinstance(current, ast.MatchAs) and current.name:
            writes[current.name].append(None)
        elif isinstance(current, ast.MatchStar) and current.name:
            writes[current.name].append(None)
        elif isinstance(current, ast.MatchMapping) and current.rest:
            writes[current.rest].append(None)

    return tuple(
        sorted(
            (name, values[0])
            for name, values in writes.items()
            if len(values) == 1 and values[0] is not None
        )
    )


def _returns_self(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    positional = [*node.args.posonlyargs, *node.args.args]
    if node.decorator_list or not positional or positional[0].arg != "self":
        return False
    required_positionals = len(positional) - len(node.args.defaults)
    if any(index < required_positionals for index in range(1, len(positional))):
        return False
    if any(default is None for default in node.args.kw_defaults):
        return False
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    return (
        len(body) == 1
        and isinstance(body[0], ast.Return)
        and isinstance(body[0].value, ast.Name)
        and body[0].value.id == "self"
    )


class _ModuleBindings(ast.NodeVisitor):
    """Record names bound at module scope without entering class/function scopes."""

    def __init__(self) -> None:
        self.bindings: dict[str, list[tuple[int, int | None]]] = defaultdict(list)

    def _add(self, name: str, node: ast.AST, alias: ast.alias | None = None) -> None:
        self.bindings[name].append((id(node), id(alias) if alias is not None else None))

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self._add(node.id, node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add(alias.asname or alias.name.split(".", 1)[0], node, alias)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self._add(alias.asname or alias.name, node, alias)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add(node.name, node)

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def _visit_comprehension_expressions(self, node: ast.AST) -> None:
        generators = node.generators
        for generator in generators:
            self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        for field_name in ("elt", "key", "value"):
            value = getattr(node, field_name, None)
            if value is not None:
                self.visit(value)

    visit_ListComp = _visit_comprehension_expressions
    visit_SetComp = _visit_comprehension_expressions
    visit_DictComp = _visit_comprehension_expressions
    visit_GeneratorExp = _visit_comprehension_expressions

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self._add(node.name, node)
        if node.type is not None:
            self.visit(node.type)
        for statement in node.body:
            self.visit(statement)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name:
            self._add(node.name, node)
        if node.pattern is not None:
            self.visit(node.pattern)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name:
            self._add(node.name, node)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest:
            self._add(node.rest, node)
        self.generic_visit(node)


def _overload_aliases(
    tree: ast.Module, module_import_ids: set[int]
) -> tuple[dict[str, str], dict[str, str]]:
    bindings = _ModuleBindings()
    bindings.visit(tree)
    module_alias_candidates: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    function_alias_candidates: dict[str, list[tuple[int, int, str]]] = defaultdict(list)

    for node in tree.body:
        if id(node) not in module_import_ids:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"typing", "typing_extensions"}:
                    bound_name = alias.asname or alias.name
                    module_alias_candidates[bound_name].append(
                        (id(node), id(alias), alias.name)
                    )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in {
            "typing",
            "typing_extensions",
        }:
            for alias in node.names:
                if alias.name == "overload":
                    bound_name = alias.asname or alias.name
                    function_alias_candidates[bound_name].append(
                        (id(node), id(alias), node.module)
                    )

    def unshadowed(candidates: dict[str, list[tuple[int, int, str]]]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for name, entries in candidates.items():
            if len(entries) != 1:
                continue
            node_id, alias_id, canonical_module = entries[0]
            if bindings.bindings.get(name) == [(node_id, alias_id)]:
                resolved[name] = canonical_module
        return resolved

    return unshadowed(module_alias_candidates), unshadowed(function_alias_candidates)


def _overload_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> OverloadSignature:
    arguments = ast.unparse(node.args)
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    signature = f"{prefix} {node.name}({arguments})"
    if node.returns is not None:
        signature += f" -> {ast.unparse(node.returns)}"
    decorator_lines = [decorator.lineno for decorator in node.decorator_list]
    start_line = min([node.lineno, *decorator_lines])
    return OverloadSignature(start_line, node.end_lineno or node.lineno, signature)


class _Extractor(ast.NodeVisitor):
    def __init__(
        self,
        file: str,
        module_import_ids: set[int],
        overload_module_aliases: dict[str, str],
        overload_function_aliases: dict[str, str],
    ):
        self.file = file
        self.module_import_ids = module_import_ids
        self.overload_module_aliases = overload_module_aliases
        self.overload_function_aliases = overload_function_aliases
        self.symbols: list[Symbol] = []
        self.imports: list[ImportRef] = []
        self.calls: list[CallSite] = []
        self.module_bindings: set[str] = set()
        self._names: list[str] = []
        self._ids: list[str] = []
        self._kinds: list[str] = []

    def _add_symbol(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
        qualname = ".".join([*self._names, node.name])
        symbol_id = f"{self.file}::{qualname}"
        decorator_refs = tuple(
            DecoratorRef(
                expression=ast.unparse(item),
                line=item.lineno,
                recognized=self._recognized_overload_decorator(item),
            )
            for item in node.decorator_list
        )
        start_line = min([node.lineno, *(item.line for item in decorator_refs)])
        is_overload = (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(item.recognized == "typing.overload" for item in decorator_refs)
        )
        overload_signature = _overload_signature(node) if is_overload else None
        local_bindings = _bindings(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else frozenset()
        local_constructors = _local_constructors(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else ()
        returns_self = (
            kind == "method"
            and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {"__enter__", "__aenter__"}
            and _returns_self(node)
        )
        self.symbols.append(
            Symbol(
                id=symbol_id,
                file=self.file,
                name=node.name,
                qualname=qualname,
                kind=kind,
                start_line=start_line,
                end_line=node.end_lineno or node.lineno,
                parent=self._ids[-1] if self._ids else None,
                local_bindings=local_bindings,
                local_constructors=local_constructors,
                returns_self=returns_self,
                is_async=isinstance(node, ast.AsyncFunctionDef),
                decorators=decorator_refs,
                is_overload=is_overload,
                overload_signature=overload_signature,
            )
        )
        self._names.append(node.name)
        self._ids.append(symbol_id)
        self._kinds.append(kind)
        for child in node.body:
            self.visit(child)
        self._names.pop()
        self._ids.pop()
        self._kinds.pop()

    def _recognized_overload_decorator(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name) and node.id in self.overload_function_aliases:
            return "typing.overload"
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.attr == "overload"
            and node.value.id in self.overload_module_aliases
        ):
            return "typing.overload"
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol(node, "class")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        kind = "method" if self._kinds and self._kinds[-1] == "class" else "function"
        self._add_symbol(node, kind)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        kind = "method" if self._kinds and self._kinds[-1] == "class" else "function"
        self._add_symbol(node, kind)

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            self.imports.append(
                ImportRef(
                    self.file,
                    item.name,
                    0,
                    None,
                    item.asname or item.name.split(".", 1)[0],
                    node.lineno,
                    self._ids[-1] if self._ids else None,
                    item.asname is not None,
                    id(node) in self.module_import_ids,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for item in node.names:
            self.imports.append(
                ImportRef(
                    self.file,
                    node.module or "",
                    node.level,
                    item.name,
                    item.asname or item.name,
                    node.lineno,
                    self._ids[-1] if self._ids else None,
                    item.asname is not None,
                    id(node) in self.module_import_ids,
                )
            )

    def visit_Call(self, node: ast.Call) -> None:
        if self._ids and self._kinds[-1] in {"function", "method"}:
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            receiver = func.value.id if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) else None
            self.calls.append(
                CallSite(self.file, self._ids[-1], ast.unparse(func), name, receiver, node.lineno, node.col_offset)
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if not self._ids and isinstance(node.ctx, (ast.Store, ast.Del)):
            self.module_bindings.add(node.id)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Lambda bodies run later; attributing their calls to the enclosing
        # function would create a false direct call edge.
        return

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        # The generator body also runs when the result is iterated later.
        return


def parse_python_file(
    root: Path, relative_path: str, root_identity: tuple[int, int] | None = None
) -> ParsedFile:
    """Parse one file; return an error record instead of stopping a scan."""
    root = Path(root).resolve() if root_identity is None else Path(root)
    path = root / relative_path
    try:
        source = read_source(root, relative_path, root_identity)
        lines = source.splitlines()
        file = FileRecord(
            path=relative_path,
            lines=len(lines),
            code_lines=sum(bool(line.strip()) and not line.lstrip().startswith("#") for line in lines),
            is_test=path.name.startswith("test_") or "tests" in path.parts or "test" in path.parts,
        )
        tree = ast.parse(source, filename=relative_path)
    except (SyntaxError, UnicodeError, OSError, ValueError) as exc:
        if "file" not in locals():
            file = FileRecord(relative_path, 0, 0, False)
        return ParsedFile(file, [], [], [], error=ParseError(relative_path, getattr(exc, "lineno", None) or 1, str(exc)))
    module_import_ids = {
        id(node) for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    }
    overload_module_aliases, overload_function_aliases = _overload_aliases(tree, module_import_ids)
    extractor = _Extractor(
        relative_path,
        module_import_ids,
        overload_module_aliases,
        overload_function_aliases,
    )
    extractor.visit(tree)
    return ParsedFile(file, extractor.symbols, extractor.imports, extractor.calls, extractor.module_bindings)
