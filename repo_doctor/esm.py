"""Resolve only unique local ESM source dependencies in the selected index."""
from dataclasses import replace
import posixpath

from collections import defaultdict

from .model import AnalysisLimit, CallEdge, ImportEdge, RepoIndex
from .scanner import discover_files


def resolve_esm_graph(index: RepoIndex, *, resolve_calls: bool = True) -> None:
    paths, _ = discover_files(index.root)
    path_set = set(paths)
    failed = {row.file for row in index.parse_errors}
    seen_limits = set(index.analysis_limits)

    def target_for(file, specifier):
        if not specifier.startswith(("./", "../")) or "\\" in specifier:
            return None, "external-or-alias"
        candidate = posixpath.normpath(posixpath.join(posixpath.dirname(file), specifier))
        options = [candidate]
        if file.endswith(".ts") and specifier.endswith(".js"):
            stem = candidate[:-3]
            options = [stem + suffix for suffix in (".ts", ".tsx", ".d.ts", ".js", ".jsx")]
        matches = [path for path in options if path in path_set]
        if len(matches) == 1 and matches[0] in index.file_languages and matches[0] not in failed:
            target = matches[0]
            if index.file_languages[target] != "python":
                return target, "unique-local-source"
        return None, "ambiguous-or-unsupported-local-source"

    edges = set(index.import_edges)
    resolved = []
    for ref in [*index.esm_imports, *index.esm_exports]:
        if ref.specifier is None:
            continue
        target, reason = target_for(ref.file, ref.specifier)
        if target is not None:
            edges.add(ImportEdge(ref.file, target, ref.start_line))
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

    def direct_target(call, caller):
        unsafe = index.unsafe_js_bindings.get(call.file, set())
        if (call.receiver is not None or not safe_symbol(caller.id)
                or call.name in caller.local_bindings or call.name in unsafe or "*" in unsafe):
            return None
        local = call.file + "::" + call.name
        imports = imports_by_alias[(call.file, call.name)]
        if not imports:
            return local if safe_symbol(local) else None
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
        return sid if safe_symbol(sid) else None

    calls = set(index.call_edges)
    for call in index.calls:
        if index.file_languages.get(call.file, "python") == "python":
            continue
        caller = index.symbols.get(call.caller)
        target = direct_target(call, caller) if caller is not None else None
        if target is not None:
            calls.add(CallEdge(call.caller, target, call.line))
        else:
            row = AnalysisLimit(call.file, call.line, "unresolved-call",
                "Call " + call.expression + " is outside unique unshadowed direct function bindings")
            if row not in seen_limits:
                index.analysis_limits.append(row)
                seen_limits.add(row)
    index.call_edges = sorted(calls, key=lambda row: (row.caller, row.callee, row.line))
