"""Typed records shared by repository analysis passes."""

from dataclasses import dataclass, field
from pathlib import Path

from .limits import AnalysisBudget


@dataclass(frozen=True, slots=True)
class FileRecord:
    path: str
    lines: int
    code_lines: int
    is_test: bool


@dataclass(frozen=True, slots=True)
class LocalConstructor:
    expression: str
    line: int
    column: int
    context_method: str | None = None


@dataclass(frozen=True, slots=True)
class ModuleInstanceBinding:
    class_name: str
    line: int
    column: int
    methods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DecoratorRef:
    expression: str
    line: int
    recognized: str | None = None


@dataclass(frozen=True, slots=True)
class CommandRegistrationCall:
    file: str
    line: int
    receiver: str
    callback: str
    caller: str | None = None
    class_owner: str | None = None
    column: int = 0


@dataclass(frozen=True, slots=True)
class AttributeRebinding:
    file: str
    line: int
    column: int
    receiver: str
    attribute: str
    owner: str | None = None
    class_owner: str | None = None


@dataclass(frozen=True, slots=True)
class OverloadSignature:
    start_line: int
    end_line: int
    signature: str


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
    local_constructors: tuple[tuple[str, LocalConstructor], ...] = ()
    returns_self: bool = False
    is_async: bool = False
    decorators: tuple[DecoratorRef, ...] = ()
    is_overload: bool = False
    overload_signature: OverloadSignature | None = None
    overloads: tuple[OverloadSignature, ...] = ()
    base_expressions: tuple[str, ...] = ()
    class_bindings: frozenset[str] = frozenset()
    reassigned_parameters: frozenset[str] = frozenset()


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
    is_unconditional_module_level: bool = False


@dataclass(frozen=True, slots=True)
class CallSite:
    file: str
    caller: str
    expression: str
    name: str
    receiver: str | None
    line: int
    column: int


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
    registration_calls: list[CommandRegistrationCall] = field(default_factory=list)
    attribute_rebindings: list[AttributeRebinding] = field(default_factory=list)
    module_instances: dict[str, ModuleInstanceBinding] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ImportEdge:
    source: str
    target: str
    line: int


@dataclass(frozen=True, slots=True)
class ExportHop:
    file: str
    name: str
    line: int


@dataclass(frozen=True, slots=True)
class SemanticEdge:
    kind: str
    target_symbol: str
    evidence_file: str
    line: int
    source_symbol: str | None = None
    source_file: str | None = None
    exported_name: str | None = None


@dataclass(frozen=True, slots=True)
class CallEdge:
    caller: str
    callee: str
    line: int
    via_reexports: tuple[ExportHop, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisLimit:
    file: str
    line: int | None
    reason: str
    message: str


@dataclass(frozen=True, slots=True)
class ESMImportRef:
    file: str
    specifier: str
    imported: str | None
    alias: str | None
    start_line: int
    end_line: int
    type_only: bool = False
    resolved_file: str | None = None
    resolution_kind: str | None = None


@dataclass(frozen=True, slots=True)
class ESMExportRef:
    file: str
    exported: str
    local_name: str | None
    specifier: str | None
    imported: str | None
    start_line: int
    end_line: int
    type_only: bool = False


@dataclass(frozen=True, slots=True)
class ESMSourceAssociation:
    file: str
    specifier: str
    target: str
    start_line: int
    end_line: int
    resolution_kind: str


@dataclass(frozen=True, slots=True)
class IdentifierUse:
    file: str
    name: str
    line: int


@dataclass(slots=True)
class JSParsedFile:
    parsed: ParsedFile
    esm_imports: list[ESMImportRef]
    esm_exports: list[ESMExportRef]
    identifier_uses: list[IdentifierUse]
    unsafe_bindings: set[str]
    class_header_spans: dict[str, tuple[int, int]]
    limits: list[AnalysisLimit]
    top_level_symbols: set[str] = field(default_factory=set)


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
    semantic_edges: list[SemanticEdge] = field(default_factory=list)
    registration_calls: list[CommandRegistrationCall] = field(default_factory=list)
    attribute_rebindings: list[AttributeRebinding] = field(default_factory=list)
    import_cycles: list[list[str]] = field(default_factory=list)
    module_instances: dict[str, dict[str, ModuleInstanceBinding]] = field(default_factory=dict)
    analysis_languages: tuple[str, ...] = ("python",)
    file_languages: dict[str, str] = field(default_factory=dict)
    analysis_limits: list[AnalysisLimit] = field(default_factory=list)
    esm_imports: list[ESMImportRef] = field(default_factory=list)
    esm_exports: list[ESMExportRef] = field(default_factory=list)
    identifier_uses: list[IdentifierUse] = field(default_factory=list)
    unsafe_js_bindings: dict[str, set[str]] = field(default_factory=dict)
    class_header_spans: dict[str, tuple[int, int]] = field(default_factory=dict)
    js_top_level_symbols: set[str] = field(default_factory=set)
    js_calls_resolved: bool = False
    esm_source_associations: dict[tuple[str, str, int], ESMSourceAssociation] = field(default_factory=dict)
    js_call_imports: dict[tuple[str, str, int], ESMImportRef] = field(default_factory=dict)
    budget: AnalysisBudget = field(default_factory=AnalysisBudget, repr=False)
    discovered_paths: tuple[str, ...] | None = None
