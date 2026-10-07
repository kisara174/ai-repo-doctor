"""Resolve only unique local ESM source dependencies in the selected index."""
from dataclasses import replace
import posixpath
from pathlib import PurePosixPath

from collections import defaultdict

from .model import AnalysisLimit, CallEdge, ESMImportRef, ESMSourceAssociation, ImportEdge, RepoIndex
from .scanner import discover_files
from .languages import language_for_path


SOURCE_SUFFIXES = ('.ts', '.js', '.mjs', '.tsx', '.jsx', '.d.ts',
                   '.mts', '.cts', '.cjs', '.d.mts', '.d.cts', '.json', '.node')


def _resolve_source(file: str, specifier: str, path_set: set[str],
                    file_languages: dict[str, str], failed: set[str]) -> tuple[str | None, str]:
    if not specifier.startswith(("./", "../")) or "\\" in specifier:
        return None, "external-or-alias"
    candidate = posixpath.normpath(posixpath.join(posixpath.dirname(file), specifier))
    if not PurePosixPath(specifier).suffix:
        if any(char in specifier for char in ('\x00', '?', '#', '%')) or specifier.endswith('/'):
            return None, 'unsupported-source-specifier'
        if candidate == '..' or candidate.startswith('../') or candidate.startswith('/'):
            return None, 'outside-source-root'
        if posixpath.normpath(candidate + '/package.json') in path_set:
            return None, 'directory-package-configuration'
        options = {candidate}
        options.update(candidate + suffix for suffix in SOURCE_SUFFIXES)
        index_options = {posixpath.normpath(candidate + '/index' + suffix) for suffix in SOURCE_SUFFIXES}
        options.update(index_options)
        matches = sorted(options.intersection(path_set))
        if not matches:
            return None, 'no-local-source-candidate'
        if len(matches) != 1:
            return None, 'ambiguous-local-source-candidates'
        target = matches[0]
        if (file_languages.get(target) not in ('javascript', 'typescript')
                or language_for_path(target) not in ('javascript', 'typescript')):
            return None, 'unselected-or-unsupported-local-source'
        if target in failed:
            return None, 'parse-error-local-source'
        kind = ('unique-directory-index-source' if target in index_options
                else 'unique-extensionless-source')
        return target, kind

    # Preserve the explicit-path and TypeScript .js substitution contract.
    options = [candidate]
    if file.endswith(".ts") and specifier.endswith(".js"):
        stem = candidate[:-3]
        options = [stem + suffix for suffix in (".ts", ".tsx", ".d.ts", ".js", ".jsx")]
    matches = [path for path in options if path in path_set]
    if len(matches) == 1 and matches[0] in file_languages and matches[0] not in failed:
        target = matches[0]
        if file_languages[target] != "python":
            return target, "unique-local-source"
    return None, "ambiguous-or-unsupported-local-source"


def resolve_esm_graph(index: RepoIndex, *, resolve_calls: bool = True) -> None:
    paths, _ = discover_files(index.root)
    path_set = set(paths)
    failed = {row.file for row in index.parse_errors}
    seen_limits = set(index.analysis_limits)
    index.esm_source_associations.clear()
    index.js_call_imports.clear()

    resolution_cache = {}
    edges = set(index.import_edges)
    resolved = []
    for ref in [*index.esm_imports, *index.esm_exports]:
        if ref.specifier is None:
            continue
        key = (ref.file, ref.specifier)
        if key not in resolution_cache:
            resolution_cache[key] = _resolve_source(ref.file, ref.specifier, path_set,
                                                    index.file_languages, failed)
        target, reason = resolution_cache[key]
        if target is not None:
            edges.add(ImportEdge(ref.file, target, ref.start_line))
            association = ESMSourceAssociation(ref.file, ref.specifier, target,
                                                ref.start_line, ref.end_line, reason)
            edge_key = (ref.file, target, ref.start_line)
            existing = index.esm_source_associations.get(edge_key)
            if existing is None or (association.specifier, association.end_line) < (existing.specifier, existing.end_line):
                index.esm_source_associations[edge_key] = association
        else:
            row = AnalysisLimit(ref.file, ref.start_line, reason, "Module " + ref.specifier + " was not resolved")
            if row not in seen_limits:
                index.analysis_limits.append(row)
                seen_limits.add(row)
        if hasattr(ref, "resolved_file"):
            resolved.append(replace(ref, resolved_file=target, resolution_kind=reason))
    index.esm_imports = resolved
    index.import_edges = sorted(edges, key=lambda row: (row.source, row.target, row.line))
    index.js_calls_resolved = resolve_calls
    if not resolve_calls:
        return

    def safe_symbol(sid):
        item = index.symbols.get(sid)
        return (item is not None and item.kind == "function"
                and sid in index.js_top_level_symbols and sid not in index.ambiguous_symbols
                and item.name not in index.unsafe_js_bindings.get(item.file, set())
                and "*" not in index.unsafe_js_bindings.get(item.file, set()))

    imports_by_alias = defaultdict(list)
    for ref in index.esm_imports:
        if ref.alias:
            imports_by_alias[(ref.file, ref.alias)].append(ref)
    exports_by_name = defaultdict(list)
    for ref in index.esm_exports:
        exports_by_name[(ref.file, ref.exported)].append(ref)

    def direct_target(call, caller) -> tuple[str, ESMImportRef | None] | None:
        unsafe = index.unsafe_js_bindings.get(call.file, set())
        if (call.receiver is not None or not safe_symbol(caller.id)
                or call.name in caller.local_bindings or call.name in unsafe or "*" in unsafe):
            return None
        local = call.file + "::" + call.name
        imports = imports_by_alias[(call.file, call.name)]
        if not imports:
            return (local, None) if safe_symbol(local) else None
        if len(imports) != 1 or local in index.symbols or local in index.ambiguous_symbols:
            return None
        ref = imports[0]
        if ref.type_only or ref.imported in (None, "*") or ref.resolved_file is None:
            return None
        exports = [row for row in exports_by_name[(ref.resolved_file, ref.imported)]]
        if len(exports) != 1:
            return None
        exported = exports[0]
        if exported.type_only or exported.specifier is not None or exported.local_name is None:
            return None
        sid = ref.resolved_file + "::" + exported.local_name
        return (sid, ref) if safe_symbol(sid) else None

    def source_key(item: ESMImportRef):
        return (item.file, item.start_line, item.end_line, item.alias or '', item.imported or '')

    calls = set(index.call_edges)
    for call in index.calls:
        if index.file_languages.get(call.file, "python") == "python":
            continue
        caller = index.symbols.get(call.caller)
        target = direct_target(call, caller) if caller is not None else None
        if target is not None:
            sid, ref = target
            calls.add(CallEdge(call.caller, sid, call.line))
            if ref is not None:
                key = (call.caller, sid, call.line)
                previous = index.js_call_imports.get(key)
                if previous is None or source_key(ref) < source_key(previous):
                    index.js_call_imports[key] = ref
        else:
            row = AnalysisLimit(call.file, call.line, "unresolved-call",
                "Call " + call.expression + " is outside unique unshadowed direct function bindings")
            if row not in seen_limits:
                index.analysis_limits.append(row)
                seen_limits.add(row)
    index.call_edges = sorted(calls, key=lambda row: (row.caller, row.callee, row.line))
