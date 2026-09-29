"""Bounded summary of resolved local production-module dependencies."""

from collections import defaultdict

from .model import RepoIndex


def build_architecture_summary(index: RepoIndex) -> dict:
    """Rank modules by distinct production files with resolved inbound edges."""
    production_files = {item.path for item in index.files if not item.is_test}
    importers: dict[str, set[str]] = defaultdict(set)
    caller_files: dict[str, set[str]] = defaultdict(set)
    evidence_by_target: dict[str, list[dict]] = defaultdict(list)
    local_import_edges = 0
    cross_file_call_edges = 0

    for edge in index.import_edges:
        if (edge.source not in production_files or edge.target not in production_files
                or edge.source == edge.target):
            continue
        local_import_edges += 1
        importers[edge.target].add(edge.source)
        evidence_by_target[edge.target].append({
            "kind": "import", "file": edge.source, "line": edge.line,
            "target": edge.target,
        })

    for edge in index.call_edges:
        caller = index.symbols.get(edge.caller)
        callee = index.symbols.get(edge.callee)
        if (
            caller is None or callee is None
            or caller.file not in production_files or callee.file not in production_files
            or caller.file == callee.file
        ):
            continue
        cross_file_call_edges += 1
        caller_files[callee.file].add(caller.file)
        evidence_by_target[callee.file].append({
            "kind": "call", "file": caller.file, "line": edge.line,
            "caller": edge.caller, "callee": edge.callee,
        })

    ranked = sorted(
        (
            (file, importers[file] | caller_files[file])
            for file in production_files
            if len(importers[file] | caller_files[file]) >= 2
        ),
        key=lambda item: (-len(item[1]), item[0]),
    )[:5]
    focus_modules = []
    for file, dependents in ranked:
        evidence = sorted(
            evidence_by_target[file],
            key=lambda item: (item["file"], item["line"], item["kind"],
                              item.get("callee", item.get("target", ""))),
        )
        focus_modules.append({
            "file": file,
            "dependent_file_count": len(dependents),
            "importer_count": len(importers[file]),
            "caller_file_count": len(caller_files[file]),
            "evidence": evidence[:10],
            "evidence_omitted": max(0, len(evidence) - 10),
        })
    return {
        "production_modules": len(production_files),
        "local_import_edges": local_import_edges,
        "cross_file_call_edges": cross_file_call_edges,
        "focus_modules": focus_modules,
    }
