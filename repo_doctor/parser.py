"""Extract Python structure without importing or executing scanned code."""

import ast
from collections import defaultdict
from pathlib import Path

from .model import CallSite, FileRecord, ImportRef, LocalConstructor, ParsedFile, ParseError, Symbol
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
    if node.decorator_list or not node.args.args or node.args.args[0].arg != "self":
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


class _Extractor(ast.NodeVisitor):
    def __init__(self, file: str):
        self.file = file
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
        decorators = [item.lineno for item in node.decorator_list]
        start_line = min([node.lineno, *decorators])
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
                ImportRef(self.file, item.name, 0, None, item.asname or item.name.split(".", 1)[0], node.lineno, self._ids[-1] if self._ids else None, item.asname is not None)
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for item in node.names:
            self.imports.append(
                ImportRef(self.file, node.module or "", node.level, item.name, item.asname or item.name, node.lineno, self._ids[-1] if self._ids else None, item.asname is not None)
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
    extractor = _Extractor(relative_path)
    extractor.visit(tree)
    return ParsedFile(file, extractor.symbols, extractor.imports, extractor.calls, extractor.module_bindings)
