"""Extract Python structure without importing or executing scanned code."""

import ast
from pathlib import Path

from .model import CallSite, FileRecord, ImportRef, ParsedFile, ParseError, Symbol
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
    return frozenset(names)


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
            self.calls.append(CallSite(self.file, self._ids[-1], ast.unparse(func), name, receiver, node.lineno))
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
