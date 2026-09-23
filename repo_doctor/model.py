"""Typed records shared by repository analysis passes."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileRecord:
    path: str
    lines: int
    code_lines: int
    is_test: bool


@dataclass(frozen=True, slots=True)
class Symbol:
    id: str
    file: str
    name: str
    qualname: str
    kind: str
    start_line: int
    end_line: int
    parent: str | None
    local_bindings: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ImportRef:
    file: str
    module: str
    level: int
    name: str | None
    alias: str
    line: int
    owner: str | None
    explicit_alias: bool = False


@dataclass(frozen=True, slots=True)
class CallSite:
    file: str
    caller: str
    expression: str
    name: str
    receiver: str | None
    line: int


@dataclass(frozen=True, slots=True)
class ParseError:
    file: str
    line: int
    message: str


@dataclass(slots=True)
class ParsedFile:
    file: FileRecord
    symbols: list[Symbol]
    imports: list[ImportRef]
    calls: list[CallSite]
    module_bindings: set[str] = field(default_factory=set)
    error: ParseError | None = None


@dataclass(frozen=True, slots=True)
class ImportEdge:
    source: str
    target: str
    line: int


@dataclass(frozen=True, slots=True)
class CallEdge:
    caller: str
    callee: str
    line: int


@dataclass(slots=True)
class RepoIndex:
    root: Path
    scan_mode: str
    root_identity: tuple[int, int]
    files: list[FileRecord] = field(default_factory=list)
    symbols: dict[str, Symbol] = field(default_factory=dict)
    ambiguous_symbols: set[str] = field(default_factory=set)
    imports: list[ImportRef] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)
    module_bindings: dict[str, set[str]] = field(default_factory=dict)
    parse_errors: list[ParseError] = field(default_factory=list)
    import_edges: list[ImportEdge] = field(default_factory=list)
    call_edges: list[CallEdge] = field(default_factory=list)
    import_cycles: list[list[str]] = field(default_factory=list)
